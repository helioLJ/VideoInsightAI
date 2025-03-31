#!/usr/bin/env python
"""
YouTube Authentication Script

This script handles the OAuth2 authentication flow with YouTube API
and generates a token.pickle file for use with the application.

Run this script once to authenticate, then the main application can
use the saved token for API access.
"""

import os
import pickle

import googleapiclient.discovery
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# Configuration
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
TOKEN_PICKLE_FILE = "token.pickle"
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


def authenticate_youtube():
    """Authenticate with YouTube API and save credentials to token.pickle."""
    creds = None

    # Check if token.pickle exists
    if os.path.exists(TOKEN_PICKLE_FILE):
        print(f"Found existing {TOKEN_PICKLE_FILE}")
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)

    # If credentials don't exist or are invalid, go through auth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                # If refresh fails, go through the full auth flow
                if os.path.exists(TOKEN_PICKLE_FILE):
                    os.remove(TOKEN_PICKLE_FILE)
                creds = None

        # If we still need to authenticate
        if not creds:
            print("Starting OAuth2 authorization flow...")
            try:
                # Verify client_secrets.json exists
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    print(f"ERROR: '{CLIENT_SECRETS_FILE}' not found.")
                    print("Please create this file with your Google API credentials.")
                    return False

                # Run the authorization flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    CLIENT_SECRETS_FILE, SCOPES
                )
                creds = flow.run_local_server(port=8080)

                # Save credentials for next run
                with open(TOKEN_PICKLE_FILE, "wb") as token:
                    pickle.dump(creds, token)
                print(f"Authentication successful! Token saved to {TOKEN_PICKLE_FILE}")
            except Exception as e:
                print(f"Authentication error: {e}")
                return False

    # Test the credentials by making a simple API call
    try:
        youtube = googleapiclient.discovery.build(
            API_SERVICE_NAME, API_VERSION, credentials=creds
        )
        request = youtube.channels().list(part="snippet", mine=True)
        response = request.execute()

        channel_name = response["items"][0]["snippet"]["title"]
        print(f"Authentication verified! Connected to channel: {channel_name}")
        print("Token is valid and working correctly.")
        return True

    except Exception as e:
        print(f"Error testing API connection: {e}")
        return False


if __name__ == "__main__":
    print("YouTube API Authentication Script")
    print("=================================")
    print("This script will authenticate your application with the YouTube API")
    print(f"and save the credentials to {TOKEN_PICKLE_FILE} for later use.")
    print("\nYou will be redirected to a Google login page in your browser.")
    print("After logging in and granting permissions, return to this terminal.")
    print("\nStarting authentication process...")

    success = authenticate_youtube()

    if success:
        print("\nSetup completed successfully!")
        print(
            f"The {TOKEN_PICKLE_FILE} file has been created and can now be used by the application."
        )
    else:
        print(
            "\nAuthentication failed. Please check the error messages above and try again."
        )
