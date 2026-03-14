import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json
import logging

# ─── Google Sheets Configuration ───
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
CREDS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "google_credentials.json"
)
SHEET_NAME = "DSC LEADS"


def _get_gspread_client():
    """Authorize and return a gspread client, with detailed logging."""
    creds_json_str = os.environ.get("GOOGLE_JSON_CREDENTIALS")
    
    if creds_json_str:
        logging.info("Found GOOGLE_JSON_CREDENTIALS environment variable.")
        try:
            creds_json = json.loads(creds_json_str)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, SCOPE)
            client = gspread.authorize(creds)
            logging.info("Successfully authorized Google Sheets client from env var.")
            return client
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse GOOGLE_JSON_CREDENTIALS: {e}")
            return None
        except Exception as e:
            logging.error(f"Failed to authorize Google Sheets client from env var: {e}")
            return None

    if os.path.exists(CREDS_FILE):
        logging.info(f"Found credentials file at: {CREDS_FILE}")
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
            client = gspread.authorize(creds)
            logging.info("Successfully authorized Google Sheets client from file.")
            return client
        except Exception as e:
            logging.error(f"Failed to authorize Google Sheets client from file: {e}")
            return None
    
    logging.error("Google credentials not found. Set GOOGLE_JSON_CREDENTIALS env var or create google_credentials.json")
    return None


def save_to_google_sheets(name, email, phone, subject, message, source):
    """
    Append a new lead to the 'DSC Leads' Google Sheet.

    Args:
        name (str): The lead's full name.
        email (str): The lead's email address.
        phone (str): The lead's phone number.
        subject (str): The subject of the inquiry.
        message (str): The lead's message.
        source (str): The form or page where the lead was generated.

    Returns:
        bool: True if the row was added successfully, False otherwise.
    """
    try:
        client = _get_gspread_client()
        if not client:
            logging.error("Aborting save to Google Sheets due to client authorization failure.")
            return False

        sheet = client.open(SHEET_NAME).sheet1
        logging.info(f"Successfully opened Google Sheet: '{SHEET_NAME}'")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, name, email, phone, subject, message, source]

        sheet.append_row(row)
        logging.info(f"Successfully saved lead from {email} to Google Sheets.")
        return True

    except gspread.exceptions.SpreadsheetNotFound:
        logging.error(f"Google Sheet '{SHEET_NAME}' not found. Please check the name and ensure the service account has access.")
        return False
    except gspread.exceptions.APIError as e:
        logging.error(f"Google Sheets API error: {e}. This may be an issue with API permissions or quotas.")
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred with Google Sheets: {e}")
        return False
