# YouTube Transcript Analyzer - Backend

The backend API for the YouTube Transcript Analyzer application, built with FastAPI, SQLAlchemy, and Google's Gemini AI.

## Features

- Robust REST API for video transcript processing and analysis
- Asynchronous task handling for long-running operations
- YouTube API integration for playlist and video data
- Transcript extraction from YouTube videos
- AI-powered content analysis with Google's Gemini
- JSON-based structured AI responses for reliable data extraction
- SQLite database for persistent storage

## Technologies Used

- **FastAPI** - Modern, high-performance web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **Google API Client** - YouTube Data API integration
- **YouTube Transcript API** - Transcript extraction
- **Google Generative AI** - Gemini AI for content analysis
- **SQLite** - Lightweight database
- **Uvicorn** - ASGI server

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI app, API endpoints
│   ├── crud.py         # Database operations
│   ├── database.py     # Database models and session
│   ├── schemas.py      # Pydantic models for API
│   └── services.py     # Core business logic
├── youtube_processed_data/ # Cache directory for processed data
├── authenticate_youtube.py # Script for YouTube API authentication
├── .env                # Environment variables
├── pyproject.toml      # Project dependencies
├── README.md           # This file
└── token.pickle        # YouTube API auth token (generated during setup)
```

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/process/` | Start processing a YouTube playlist |
| GET | `/status/{task_id}` | Check processing status |
| GET | `/videos/` | Get list of processed videos |
| GET | `/videos/{video_id}` | Get detailed information for a video |

### Schemas

#### ProcessingStatus
```json
{
  "message": "string",
  "processed_count": 0,
  "skipped_count": 0,
  "failed_count": 0,
  "current_video_id": "string",
  "current_video_title": "string"
}
```

#### VideoResponse
```json
{
  "videoId": "string",
  "playlistId": "string",
  "title": "string",
  "fetch_timestamp_utc": "2023-01-01T00:00:00Z",
  "analysis": {
    "core_topic": "string",
    "summary": "string",
    "structure": "string",
    "takeaways": ["string"],
    "categories": ["string"],
    "verdict": "string",
    "justification": "string"
  },
  "has_transcript": true
}
```

## Setup and Installation

### Prerequisites

- Python 3.13+ with `uv` package manager
- Google Cloud Project with YouTube Data API enabled
- Google API credentials (OAuth client ID for desktop)
- Gemini API key

### Installation

1. Clone the repository and navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and Install dependencies using uv:
   ```bash
   uv sync
   ```

3. Set up API credentials:

   a. Create a `client_secrets.json` file in the backend directory with your Google API credentials (or just download it from the Google Cloud Console):
   ```json
   {
     "installed": {
       "client_id": "YOUR_CLIENT_ID",
       "project_id": "YOUR_PROJECT_ID",
       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
       "token_uri": "https://oauth2.googleapis.com/token",
       "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
       "client_secret": "YOUR_CLIENT_SECRET",
       "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
     }
   }
   ```

   b. Create a `.env` file with your Gemini API key:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   ```

### YouTube Authentication (One-time Setup)

The application requires YouTube API authentication to access playlist data. You'll need to run the authentication script once before starting the application:

1. Run the authentication script:
   ```bash
   uv run authenticate_youtube.py
   ```

2. A browser window will open, prompting you to sign in with your Google account and grant access to your YouTube data.

3. After you grant permission, the script will create a `token.pickle` file in the backend directory. This token will be used by the application to make YouTube API requests without requiring login each time.

4. You should see a success message in the terminal. If you encounter any errors, check that your `client_secrets.json` file is correctly configured.

> **Note:** The `token.pickle` file contains sensitive authentication information. Do not share or commit this file to version control. If you need to regenerate the token (e.g., if it expires or is revoked), simply run the authentication script again.

5. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

6. Access the API at [http://localhost:8000](http://localhost:8000)

## Development

### API Documentation

FastAPI automatically generates interactive API documentation:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Database

The application uses SQLite with SQLAlchemy ORM. The database file will be created automatically at `data/youtube_data.db`.

To modify the database schema:
1. Update models in `database.py`
2. Restart the application to apply changes (or implement a migration system for production)

### Gemini AI Integration

The application uses Google's Gemini AI model to analyze video transcripts. The implementation:

1. Prompts Gemini to provide analysis in a structured JSON format
2. Includes fields for core topic, summary, structure, takeaways, categories, verdict, and justification
3. Uses a robust multi-stage parser that:
   - First attempts to parse the JSON response directly
   - Falls back to regex-based parsing if JSON parsing fails
   - Includes smart category extraction to ensure categories are always provided
   - Handles edge cases like string-encoded arrays and different formatting styles

This approach ensures more reliable and consistent analysis outputs compared to free-text parsing.

### Processing Flow

1. User submits a playlist ID
2. Backend fetches video IDs from the playlist
3. For each video:
   - Fetch transcript using YouTube Transcript API
   - Send transcript to Gemini AI for structured JSON analysis
   - Parse the response and extract all components
   - Store results in the database
4. Frontend polls for status and displays results

## Troubleshooting

- **YouTube Authentication**: If you encounter authentication errors, try:
  - Delete the `token.pickle` file and run `python authenticate_youtube.py` again
  - Verify your Google Cloud project has the YouTube Data API v3 enabled
  - Check that your OAuth credentials are properly configured for a desktop application
  - Ensure you're signing in with a Google account that has access to YouTube

- **Transcript Fetch Failures**: Some videos may have disabled transcripts or unsupported languages
- **Gemini API Errors**: Check your API key and quota limits
- **Database Issues**: If schema changes cause errors, try deleting the database file and restarting
- **Missing Categories**: If categories are missing in the analysis, the system will attempt to generate them based on the content, but you can also reprocess the video to get a new analysis

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `MAX_VIDEOS_TO_PROCESS` | (Optional) Limit the number of videos processed per playlist |
| `DATABASE_URL` | (Optional) Override the default SQLite database URL |
