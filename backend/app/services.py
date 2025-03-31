import asyncio
import json
import os
import pickle
import re
from datetime import datetime
from typing import Any

import google.generativeai as genai
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

from . import crud, schemas

# --- YouTube Authentication ---
youtube_service = None
TOKEN_PICKLE_FILE = "token.pickle"
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def initialize_youtube_service():
    """Initialize YouTube API service using existing credentials from token.pickle.

    This function assumes authenticate_youtube.py has been run once to generate
    the token.pickle file. It does not initiate the full OAuth flow.
    """
    global youtube_service
    creds = None

    # Check if token.pickle exists
    if not os.path.exists(TOKEN_PICKLE_FILE):
        print(f"ERROR: '{TOKEN_PICKLE_FILE}' not found.")
        print(
            "Please run 'python authenticate_youtube.py' first to generate the token."
        )
        print("See README.md for instructions on YouTube authentication.")
        return None

    # Load credentials from token file
    try:
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)
    except Exception as e:
        print(f"Error loading token: {e}")
        print("Please run 'python authenticate_youtube.py' to generate a new token.")
        return None

    # Refresh token if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save the refreshed credentials
            with open(TOKEN_PICKLE_FILE, "wb") as token:
                pickle.dump(creds, token)
        except Exception as e:
            print(f"Error refreshing token: {e}")
            print(
                "Please run 'python authenticate_youtube.py' to generate a new token."
            )
            return None

    # Build and return the YouTube service
    try:
        youtube_service = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=creds
        )
        print("YouTube API service created successfully.")
        return youtube_service
    except Exception as e:
        print(f"Failed to build YouTube service: {e}")
        return None


def get_playlist_video_ids(service, playlist_id):
    """Fetches all video IDs from a given playlist, handling pagination."""
    video_ids = []
    next_page_token = None
    print(f"Fetching video IDs from playlist: {playlist_id}...")

    while True:
        try:
            request = service.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            response = request.execute()
            current_page_items = response.get("items", [])

            for item in current_page_items:
                video_id = item.get("contentDetails", {}).get("videoId")
                if video_id:
                    video_ids.append(video_id)

            next_page_token = response.get("nextPageToken")
            print(
                f"Fetched {len(current_page_items)} items. Total unique IDs collected so far: {len(video_ids)}"
            )

            if not next_page_token:
                break
        except googleapiclient.errors.HttpError as e:
            print(f"An API error occurred while fetching playlist items: {e}")
            if e.resp.status in [403, 404]:
                print(f"Error {e.resp.status}: Check permissions or playlist ID.")
            break
        except Exception as e:
            print(f"An unexpected error occurred fetching playlist items: {e}")
            break

    print(
        f"Finished fetching. Found {len(video_ids)} total unique video IDs in the playlist."
    )
    return video_ids


def get_video_details(service, video_ids):
    """Fetches details (like title) for a list of video IDs."""
    video_details = {}
    print(f"Fetching details for {len(video_ids)} video IDs...")
    for i in range(0, len(video_ids), 50):
        chunk_ids = video_ids[i : i + 50]
        try:
            request = service.videos().list(part="snippet", id=",".join(chunk_ids))
            response = request.execute()
            for item in response.get("items", []):
                vid_id = item["id"]
                title = item.get("snippet", {}).get("title", f"Untitled_{vid_id}")
                video_details[vid_id] = title
            print(f"  Fetched details for chunk {i // 50 + 1}...")
        except googleapiclient.errors.HttpError as e:
            print(f"  An API error occurred fetching video details chunk: {e}")
            for vid_id in chunk_ids:
                video_details.setdefault(vid_id, f"ErrorFetchingTitle_{vid_id}")
        except Exception as e:
            print(f"  An unexpected error occurred fetching video details chunk: {e}")
            for vid_id in chunk_ids:
                video_details.setdefault(vid_id, f"ErrorFetchingTitle_{vid_id}")
    print(f"Finished fetching details for {len(video_details)} videos.")
    return video_details


# --- Transcript Fetching ---
async def fetch_transcript(video_id: str) -> str | None:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        transcript = None
        preferred_langs = ["en", "pt"]
        try:
            transcript = transcript_list.find_manually_created_transcript(
                preferred_langs
            )
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(preferred_langs)
            except NoTranscriptFound:
                try:
                    available_lang_codes = [t.language_code for t in transcript_list]
                    if available_lang_codes:
                        transcript = transcript_list.find_transcript(
                            available_lang_codes
                        )
                except NoTranscriptFound:
                    pass  # No transcript found at all

        if transcript:
            full_transcript_segments = transcript.fetch()

            # Fix: Use dot notation or check if segment is object or dictionary
            transcript_text = ""
            for segment in full_transcript_segments:
                if hasattr(segment, "text"):
                    # Access as object
                    transcript_text += segment.text + "\n"
                elif isinstance(segment, dict):
                    # Access as dictionary
                    transcript_text += segment.get("text", "") + "\n"

            print(
                f"    -> Transcript fetched successfully ({transcript.language_code})."
            )
            return transcript_text
        else:
            print("    -> No suitable transcript found.")
            return None

    except TranscriptsDisabled:
        print(f"    -> Transcripts are disabled for video ID: {video_id}")
        return None
    except NoTranscriptFound:
        print(
            f"    -> No transcript found (list_transcripts call) for video ID: {video_id}"
        )
        return None
    except Exception as e:
        print(
            f"    -> An UNEXPECTED error occurred fetching transcript for {video_id}: {e}"
        )
        return None


# --- Gemini Analysis ---
async def analyze_transcript_with_gemini(
    transcript_text: str,
) -> schemas.VideoAnalysis | None:
    if not GEMINI_API_KEY or not transcript_text:
        return None
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Enhanced prompt requesting JSON output
        prompt = f"""**Objective:** Analyze the following YouTube video transcript to help someone efficiently decide if they should invest time watching the full video or if understanding the summary is sufficient.

**Your Role:** Act as an expert content analyst. Focus only on the information present in the text.

**Transcript:**
--- TRANSCRIPT START ---
{transcript_text[:200000]}
--- TRANSCRIPT END ---

**Analysis Request:**
Please analyze this transcript and provide your analysis as a JSON object with the following structure:

```json
{{
  "core_topic": "In 1-2 sentences, what is the central subject matter and the primary goal or thesis of the video based on this transcript?",
  "summary": "Provide a comprehensive and detailed summary that covers the main arguments, information points, or narrative arc presented. Go beyond a minimal overview; capture the essence and flow. Use bullet points to list key points or stages if appropriate for the content structure.",
  "structure": "Briefly mention the apparent structure (e.g., tutorial steps, discussion between speakers, historical overview, comparison, argument/counter-argument, presentation with examples).",
  "takeaways": [ # List distinct key takeaways, conclusions, or actionable insights presented in the transcript
    "Key takeaway 1",
    "Key takeaway 2",
    "Key takeaway 3",
    "Key takeaway 4"
  ],
  "categories": [ # Suggest specific and relevant keywords or topic categories that accurately classify this content.
    "Category 1",
    "Category 2",
    "Category 3",
    "Category 4",
    "Category 5"
  ],
  "verdict": "Either 'Worth Watching' or 'Summary Sufficient'",
  "justification": "A concise explanation for the verdict"
}}
```

Your response should ONLY contain this valid JSON object, nothing else. 
The categories field MUST be present and contain at least 3 category tags relevant to the content.
The takeaways should be the most important insights from the video.
For the verdict field, use EXACTLY "Worth Watching" or "Summary Sufficient".
"""

        response = await model.generate_content_async(prompt)
        analysis_text = response.text
        # --- PARSE THE RESPONSE TEXT ---
        parsed_analysis = parse_gemini_output(analysis_text)
        return schemas.VideoAnalysis(**parsed_analysis)

    except Exception as e:
        print(f"Error during Gemini analysis: {e}")
        return None


def parse_gemini_output(text: str) -> dict[str, Any]:
    """Parse the Gemini API output text into structured analysis components.
    First tries to parse as JSON, falls back to regex parsing as a backup."""
    analysis = {
        "core_topic": None,
        "summary": None,
        "structure": None,
        "takeaways": [],
        "categories": [],
        "verdict": None,
        "justification": None,
    }

    try:
        # First, try to extract JSON from the text
        # Look for content within code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            try:
                parsed_json = json.loads(json_str)
                print("Successfully parsed JSON response")
                
                # Map JSON fields to our analysis dict
                for key in analysis:
                    if key in parsed_json:
                        analysis[key] = parsed_json[key]
                
                # Ensure categories is a list
                if isinstance(analysis["categories"], str):
                    # Try to parse as JSON array
                    try:
                        analysis["categories"] = json.loads(analysis["categories"])
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"Error parsing categories: {e}")
                        # Split by commas as fallback
                        analysis["categories"] = [c.strip() for c in analysis["categories"].split(",")]
                
                # Ensure takeaways is a list
                if isinstance(analysis["takeaways"], str):
                    # Try to parse as JSON array
                    try:
                        analysis["takeaways"] = json.loads(analysis["takeaways"])
                    except (json.JSONDecodeError, TypeError) as e:
                        print(f"Error parsing takeaways: {e}")
                        # Split by new lines as fallback
                        analysis["takeaways"] = [t.strip() for t in analysis["takeaways"].split("\n")]
                
                # If we successfully extracted the JSON data, return it
                if any(analysis.values()):
                    print(f"Categories from JSON: {analysis['categories']}")
                    return analysis
            except json.JSONDecodeError as e:
                print(f"JSON decoding error: {e}, falling back to regex parsing")
        
        # If no JSON in code blocks, try to find JSON directly in the text
        try:
            # Try to find a JSON object anywhere in the text
            json_pattern = r"(\{(?:[^{}]|(?:\{[^{}]*\}))*\})"
            json_matches = re.findall(json_pattern, text)
            
            if json_matches:
                for potential_json in json_matches:
                    try:
                        parsed_json = json.loads(potential_json)
                        # Check if this looks like our expected structure
                        if any(key in parsed_json for key in analysis):
                            print("Found JSON object in text")
                            # Map JSON fields to our analysis dict
                            for key in analysis:
                                if key in parsed_json:
                                    analysis[key] = parsed_json[key]
                            
                            # If we found valid data, break out of the loop
                            if any(analysis.values()):
                                print(f"Categories from inline JSON: {analysis['categories']}")
                                return analysis
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error trying to find JSON in text: {e}")
        
        # If JSON parsing failed or didn't yield results, fall back to our existing regex-based parser
        print("JSON parsing failed or incomplete, falling back to regex parsing")
                
        # Use the existing regex-based parsing code as a fallback
        # First, try to extract main sections
        section_patterns = [
            # Bold numbered headings: **1. Core Topic & Purpose:**
            r"\*\*\d+\.\s+([\w\s&]+):\*\*\s*(.*?)(?=\*\*\d+\.|$)",
            # Numbered headings without bold: 1. Core Topic & Purpose:
            r"\n\d+\.\s+([\w\s&]+):\s*(.*?)(?=\n\d+\.|$)",
            # Bold headings without numbers: **Core Topic & Purpose:**
            r"\*\*([\w\s&]+):\*\*\s*(.*?)(?=\*\*[\w\s&]+:|$)",
            # Simple headings: Core Topic & Purpose:
            r"\n([\w\s&]+):\s*(.*?)(?=\n[\w\s&]+:|$)",
        ]

        sections = {}
        for pattern in section_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                for heading, content in matches:
                    heading = heading.strip().lower()
                    content = content.strip()
                    sections[heading] = content
                # If we found sections with this pattern, stop trying other patterns
                break

        # Extract core topic section
        for key in ["core topic & purpose", "core topic", "topic", "purpose"]:
            if key in sections:
                analysis["core_topic"] = sections[key]
                break

        # Extract summary section
        for key in [
            "detailed summary & structure",
            "summary & structure",
            "summary",
            "detailed summary",
        ]:
            if key in sections:
                analysis["summary"] = sections[key]
                break

        # Extract structure if available
        for key in ["structure"]:
            if key in sections:
                analysis["structure"] = sections[key]
                break

        # Extract takeaways
        for key in ["key takeaways", "takeaways"]:
            if key in sections:
                takeaways_text = sections[key]
                # Try to split by bullet points, numbered items, or new lines
                if "*" in takeaways_text:
                    items = [
                        item.strip()
                        for item in takeaways_text.split("*")
                        if item.strip()
                    ]
                elif re.search(r"\d+\.", takeaways_text):
                    items = [
                        item.strip()
                        for item in re.split(r"\d+\.", takeaways_text)
                        if item.strip()
                    ]
                else:
                    items = [
                        item.strip()
                        for item in takeaways_text.split("\n")
                        if item.strip()
                    ]
                analysis["takeaways"] = items
                break

        # Extract categories - more thorough approach
        # First try to find categories section using various names
        categories_found = False
        for key in ["categories/tags", "categories", "tags"]:
            if key in sections:
                categories_text = sections[key]
                # Try to split by bullet points, numbered items, or new lines
                items = []
                
                # Method 1: Split by asterisks (most common format from Gemini)
                if "*" in categories_text:
                    items = [
                        item.strip()
                        for item in categories_text.split("*")
                        if item.strip()
                    ]
                
                # Method 2: Extract bullet points with regex
                if not items:
                    bullet_items = re.findall(r"[-*•]\s*([^\n]+)", categories_text)
                    if bullet_items:
                        items = [item.strip() for item in bullet_items]
                
                # Method 3: Split by numbered items
                if not items and re.search(r"\d+\.", categories_text):
                    items = [
                        item.strip()
                        for item in re.split(r"\d+\.", categories_text)
                        if item.strip()
                    ]
                
                # Method 4: Split by newlines
                if not items:
                    items = [
                        item.strip()
                        for item in categories_text.split("\n")
                        if item.strip()
                    ]

                # Method 5: Split by commas (last resort)
                if not items and "," in categories_text:
                    items = [
                        item.strip()
                        for item in categories_text.split(",")
                        if item.strip()
                    ]

                if items:
                    analysis["categories"] = items
                    categories_found = True
                    break
        
        # If we didn't find categories yet, try direct pattern matching
        if not categories_found:
            # Look for categories in the full text with direct pattern matching
            categories_section = re.search(
                r"categ[^:]*:?\s*(.*?)(?=\n\s*\n|$)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if categories_section:
                cat_text = categories_section.group(1)
                
                # Try bullet patterns first
                cat_items = re.findall(r"[-*•]\s*([^\n]+)", cat_text)
                if cat_items:
                    analysis["categories"] = [item.strip() for item in cat_items if item.strip()]
                # If no bullet items, try by lines
                elif not analysis["categories"]:
                    analysis["categories"] = [
                        line.strip() 
                        for line in cat_text.split("\n") 
                        if line.strip() and not line.strip().startswith("•") and not line.strip().startswith("*")
                    ]
            
            # If still no categories, try to extract from any lists in the text
            if not analysis["categories"]:
                # Look for list-like structures that might be categories
                category_candidates = re.findall(r"(?:Film|TV|Comedy|Documentary|Genre|Topic|Subject|Media|Video|Content|Category|Classification)(?::|-)?\s+([^\n,]+)", text, re.IGNORECASE)
                if category_candidates:
                    analysis["categories"] = [item.strip() for item in category_candidates if item.strip()]

        # Extract verdict and justification
        for key in ["watch value assessment", "verdict assessment", "assessment"]:
            if key in sections:
                assessment_text = sections[key]

                # Look for verdict
                verdict_match = re.search(
                    r"verdict:?\s*([^\.]+)", assessment_text, re.IGNORECASE
                )
                if verdict_match:
                    analysis["verdict"] = verdict_match.group(1).strip()

                # Look for justification
                just_match = re.search(
                    r"justification:?\s*(.+)", assessment_text, re.IGNORECASE
                )
                if just_match:
                    analysis["justification"] = just_match.group(1).strip()

                # If no explicit justification found, use the rest of the assessment as justification
                if not analysis["justification"] and analysis["verdict"]:
                    verdict_index = assessment_text.lower().find("verdict")
                    if verdict_index > -1:
                        after_verdict = assessment_text[verdict_index:].split("\n", 1)
                        if len(after_verdict) > 1:
                            analysis["justification"] = after_verdict[1].strip()
                break

        # If we still don't have a verdict, look for worth watching or summary sufficient patterns
        if not analysis["verdict"]:
            if re.search(r"worth\s+watching", text, re.IGNORECASE):
                analysis["verdict"] = "Worth Watching"
            elif re.search(r"summary\s+sufficient", text, re.IGNORECASE):
                analysis["verdict"] = "Summary Sufficient"

        # If sections extraction failed or sections are empty, try direct pattern matching
        if not any(analysis.values()):
            print("Section extraction failed, trying direct pattern matching...")

            # Direct pattern matching for core topic
            core_topic_match = re.search(
                r"core topic[^:]*:?\s*([^\n]+)", text, re.IGNORECASE
            )
            if core_topic_match:
                analysis["core_topic"] = core_topic_match.group(1).strip()

            # Direct pattern matching for takeaways
            takeaways_section = re.search(
                r"key takeaways[^:]*:?\s*(.*?)(?=\n\s*\n|$)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if takeaways_section:
                takeaways_text = takeaways_section.group(1)
                takeaways = [
                    t.strip() for t in re.findall(r"[-*•]\s*([^\n]+)", takeaways_text)
                ]
                if takeaways:
                    analysis["takeaways"] = takeaways

            # Direct pattern matching for verdict
            verdict_match = re.search(r"verdict:?\s*([^\n\.]+)", text, re.IGNORECASE)
            if verdict_match:
                analysis["verdict"] = verdict_match.group(1).strip()

        # Clean up values
        for key in analysis:
            if isinstance(analysis[key], str):
                analysis[key] = analysis[key].strip()
            elif isinstance(analysis[key], list):
                analysis[key] = [item.strip() for item in analysis[key] if item.strip()]
                
        # If categories are still empty, add some default ones based on content
        if not analysis["categories"] and analysis["core_topic"]:
            # Generate some categories based on the core topic
            try:
                topic_words = analysis["core_topic"].lower()
                
                # Common video categories to check for
                category_keywords = {
                    "review": ["review", "critique", "analysis"],
                    "tutorial": ["tutorial", "guide", "how to", "learn", "teaching"],
                    "comedy": ["comedy", "comedic", "humor", "funny", "joke"],
                    "documentary": ["documentary", "history", "historical", "real"],
                    "educational": ["education", "educational", "lecture", "learn"],
                    "entertainment": ["entertainment", "show", "performance"],
                    "music": ["music", "song", "concert", "musician", "band"],
                    "technology": ["tech", "technology", "software", "hardware", "digital"],
                    "gaming": ["game", "gaming", "video game", "gameplay"],
                    "film": ["film", "movie", "cinema", "director", "actor"],
                    "television": ["tv", "television", "show", "series", "episode"]
                }
                
                extracted_categories = []
                for category, keywords in category_keywords.items():
                    if any(keyword in topic_words for keyword in keywords):
                        extracted_categories.append(category.title())
                
                if extracted_categories:
                    if len(extracted_categories) > 5:
                        extracted_categories = extracted_categories[:5]  # Limit to 5 categories
                    analysis["categories"] = extracted_categories
                elif analysis["verdict"]:
                    # If verdict exists but no categories, add at least a basic viewing category
                    analysis["categories"] = ["Content Analysis"]
            except Exception as e:
                print(f"Error generating default categories: {e}")
                # If all else fails, set a generic category
                analysis["categories"] = ["Video Content"]

        # Report if we were able to extract at least some information
        if any(analysis.values()):
            print("Successfully extracted some analysis information.")
            print(f"Categories found: {analysis['categories']}")
        else:
            print("Warning: Could not parse Gemini output structure.")

    except Exception as e:
        print(f"Error parsing Gemini output: {e}")
        # Log a portion of the text that caused the error
        print(f"Text excerpt: {text[:150]}...")
        # Set default categories if we hit an error
        analysis["categories"] = ["Video Content"]

    return analysis


# --- Main Processing Logic ---
# This function will be called as a background task
async def process_playlist_videos(
    db: AsyncSession, playlist_id: str, status_tracker: dict
):
    global youtube_service
    if not youtube_service:
        initialize_youtube_service()
    if not youtube_service:
        status_tracker["message"] = "Error: YouTube Service not initialized."
        return

    status_tracker["message"] = f"Fetching video IDs for playlist {playlist_id}..."
    # Adapt get_playlist_video_ids to be async or run in threadpool
    video_ids = get_playlist_video_ids(
        youtube_service, playlist_id
    )  # Assume sync for now
    if not video_ids:
        status_tracker["message"] = "No videos found in playlist or failed to fetch."
        return

    # Fetch titles (sync for now)
    video_titles = get_video_details(youtube_service, video_ids)

    total_videos = len(video_ids)
    status_tracker["processed_count"] = 0
    status_tracker["skipped_count"] = 0
    status_tracker["failed_count"] = 0

    for i, video_id in enumerate(video_ids):
        status_tracker["message"] = f"Processing video {i + 1}/{total_videos}"
        status_tracker["current_video_id"] = video_id
        status_tracker["current_video_title"] = video_titles.get(
            video_id, "Unknown Title"
        )

        existing_video = await crud.get_video(db, video_id)
        if (
            existing_video and existing_video.analysis_summary
        ):  # Check if analysis exists
            status_tracker["skipped_count"] += 1
            continue

        transcript = await fetch_transcript(video_id)  # Needs async adaptation
        if not transcript:
            status_tracker["failed_count"] += 1
            # Optionally save basic video info without transcript/analysis
            video_data = {
                "videoId": video_id,
                "playlistId": playlist_id,
                "title": video_titles.get(video_id),
                "fetch_timestamp_utc": datetime.utcnow(),
                "transcript": None,
            }
            await crud.create_or_update_video(db, video_data)
            continue

        analysis_obj = await analyze_transcript_with_gemini(transcript)
        if not analysis_obj:
            status_tracker["failed_count"] += 1
            # Save with transcript but no analysis
            video_data = {
                "videoId": video_id,
                "playlistId": playlist_id,
                "title": video_titles.get(video_id),
                "fetch_timestamp_utc": datetime.utcnow(),
                "transcript": transcript,
                # Add empty analysis fields
                **schemas.VideoAnalysis().model_dump(),
            }
            await crud.create_or_update_video(db, video_data)
            continue

        # Save complete data
        video_data = {
            "videoId": video_id,
            "playlistId": playlist_id,
            "title": video_titles.get(video_id),
            "fetch_timestamp_utc": datetime.utcnow(),
            "transcript": transcript,
            # Unpack the parsed analysis object
            **{
                f"analysis_{k}": v
                for k, v in analysis_obj.model_dump().items()
                if v is not None
            },
        }
        await crud.create_or_update_video(db, video_data)
        status_tracker["processed_count"] += 1
        await asyncio.sleep(1)  # Rate limit Gemini calls

    status_tracker["message"] = "Processing complete."
    status_tracker["current_video_id"] = None
    status_tracker["current_video_title"] = None
