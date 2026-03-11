import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

# ─── Google Sheets Configuration ───
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
CREDS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "google_credentials.json"
)
SHEET_NAME = "DSC Leads"


def _get_gspread_client():
    """Authorize and return a gspread client."""
    if not os.path.exists(CREDS_FILE):
        print(f"[ERROR] Google credentials not found at: {CREDS_FILE}")
        return None

    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"[ERROR] Failed to authorize Google Sheets client: {e}")
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
            return False

        sheet = client.open(SHEET_NAME).sheet1

        # Prepare the row data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, name, email, phone, subject, message, source]

        # Append the row to the sheet
        sheet.append_row(row)
        print(f"Successfully saved lead from {email} to Google Sheets.")
        return True

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"[ERROR] Google Sheet '{SHEET_NAME}' not found. Please create it.")
        return False
    except gspread.exceptions.APIError as e:
        print(f"[ERROR] Google Sheets API error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred with Google Sheets: {e}")
        return False
