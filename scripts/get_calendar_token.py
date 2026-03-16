"""
One-time OAuth2 flow to generate GOOGLE_CALENDAR_TOKEN_JSON.

Usage:
    1. Create a GCP OAuth2 client (Desktop app) and download credentials.json
    2. Run: python scripts/get_calendar_token.py
    3. Complete the browser auth flow
    4. Copy the printed JSON into your .env as GOOGLE_CALENDAR_TOKEN_JSON=...

Requires: google-auth-oauthlib (already in requirements.txt)
"""
import json
import os
import sys

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit("Run: pip install google-auth-oauthlib")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]
CREDENTIALS_FILE = os.getenv("GOOGLE_OAUTH_CREDENTIALS", "credentials.json")

if not os.path.exists(CREDENTIALS_FILE):
    sys.exit(
        f"Missing {CREDENTIALS_FILE}.\n"
        "Download it from GCP Console → APIs & Services → Credentials → "
        "OAuth 2.0 Client IDs → Desktop app → Download JSON."
    )

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

token_dict = {
    "token":         creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri":     creds.token_uri,
    "client_id":     creds.client_id,
    "client_secret": creds.client_secret,
    "scopes":        list(creds.scopes),
}

print("\n--- Copy this into your .env ---")
print(f"GOOGLE_CALENDAR_TOKEN_JSON={json.dumps(token_dict)}")
print("--- End ---\n")
