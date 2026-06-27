from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

import os
import json
import threading

_sheets_client = None
_sheets_sheet = None
_sheets_lock = threading.Lock()

def _get_sheets():
    global _sheets_client, _sheets_sheet
    if _sheets_sheet is not None:
        return _sheets_sheet
    with _sheets_lock:
        if _sheets_sheet is not None:
            return _sheets_sheet
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON environment variable is not set. "
            "Set it to the raw JSON string or a file path containing the "
            "Google service account credentials."
        )
    if os.path.isfile(raw):
        with open(raw) as f:
            service_account_info = json.load(f)
    else:
        service_account_info = json.loads(raw)
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    _sheets_client = gspread.authorize(creds)
    _sheets_sheet = _sheets_client.open_by_key(
        "1JgAfy93z1Tiqno-suJXKXfP6iLUR3mNzWnATD4TIuSY"
    ).sheet1
    return _sheets_sheet


# CLEAN LEAD DATA
def normalize_date(raw: str) -> str:
    """Convert any common date format to YYYY-MM-DD."""
    raw = raw.strip().split(" ")[0].split("T")[0]
    if not raw:
        return ""
    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw
    # MM/DD/YYYY or M/D/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return raw


def _safe_int(value, default=0):
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default


def _get_ci(d, key, default=""):
    """Get value from dict by case-insensitive key lookup."""
    if key in d:
        return d[key]
    lower = key.lower()
    for k, v in d.items():
        if k.lower() == lower:
            return v
    return default


def clean_lead_data(lead):

    raw_email_sent = str(
        lead.get("email_sent_at", "")
    ).strip()

    return {

        "lead_id": str(
            lead.get("lead_id", "")
        ).strip(),

        "name": str(
            lead.get("name", "")
        ).strip(),

        "email": str(
            lead.get("email", "")
        ).strip(),

        "company": str(
            lead.get("company", "")
        ).strip(),

        "email_sent_at": normalize_date(raw_email_sent),

        "email_sent_at_raw": raw_email_sent,

        "sequence_step": _safe_int(
            lead.get("sequence_step", 0)
        ),

        "replied": str(
            lead.get("replied", "")
        ).strip().upper() == "TRUE",

        # NEW FIELD
        "tier": str(
            lead.get("tier", "")
        ).strip(),

        # NEW FIELD
        "subject_line": str(
            lead.get("subject_line", "")
        ).strip(),

        # NEW FIELD
        "opt_out": str(
            lead.get("opt_out", "")
        ).strip().upper() == "TRUE",

        # NEW FIELD
        "reply_snippet": str(
            _get_ci(lead, "reply_content") or
            _get_ci(lead, "reply_snippet") or
            _get_ci(lead, "snippet") or
            _get_ci(lead, "reply") or
            ""
        ).strip()
    }


# GET ALL LEADS
def get_all_leads():

    sheet = _get_sheets()
    records = sheet.get_all_records()

    leads = []

    for row in records:

        lead = clean_lead_data(row)

        leads.append(lead)

    return leads


# GET PENDING LEADS
def get_pending_leads():

    leads = get_all_leads()

    pending = []

    for lead in leads:

        # Skip replied leads
        if lead["replied"]:
            continue

        # Skip unsubscribed / opted out leads
        if lead["opt_out"]:
            continue

        pending.append(lead)

    return pending


# GET LEAD BY ID
def get_lead_by_id(lead_id):

    leads = get_all_leads()

    for lead in leads:

        if str(lead["lead_id"]) == str(lead_id):

            return lead

    return None

# BULK ADD LEADS
def bulk_add_leads(list_of_rows):
    """
    Add multiple leads to Google Sheets in a single API call.

    Prevents duplicate emails from being added.
    """

    try:

        # Get existing emails from sheet
        records = _get_sheets().get_all_records()

        existing_emails = {
            str(row.get("email", "")).strip().lower()
            for row in records
            if row.get("email")
        }

        filtered_rows = []
        duplicate_count = 0

        for row in list_of_rows:

            # Email column = index 2
            email = str(row[2]).strip().lower()

            if email in existing_emails:
                duplicate_count += 1
                continue

            existing_emails.add(email)

            filtered_rows.append(row)

        if not filtered_rows:

            return {"added": 0, "skipped": duplicate_count}

        _get_sheets().append_rows(
            filtered_rows,
            value_input_option="USER_ENTERED"
        )

        return {"added": len(filtered_rows), "skipped": duplicate_count}

    except Exception as error:

        logger.error(
            f"Failed to bulk add leads: {error}"
        )

        return False

# MARK EMAIL SENT
def mark_email_sent(
    lead_id,
    sequence_step,
    tier="",
    subject_line=""
):

    sheet = _get_sheets()
    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):

        if str(row.get("lead_id", "")) == str(lead_id):

            current_time = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            try:

                # Column 5 = email_sent_at
                sheet.update_cell(index, 5, current_time)

                # Column 6 = sequence_step
                sheet.update_cell(index, 6, sequence_step)

                # Column 8 = tier
                sheet.update_cell(index, 8, tier)

                # Column 9 = subject_line
                sheet.update_cell(index, 9, subject_line)

                logger.info(f"Updated lead {lead_id}")

                return True

            except Exception as error:

                logger.error(f"Failed to update lead: {error}")

                return False

    logger.warning("Lead not found")

    return False


# MARK REPLIED
def mark_replied(
    lead_id,
    snippet=None,
    is_opt_out=False
):

    sheet = _get_sheets()
    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):

        if str(row.get("lead_id", "")) == str(lead_id):

            try:

                # Column 7 = replied
                sheet.update_cell(index, 7, "TRUE")

                # Column 10 = opt_out
                sheet.update_cell(
                    index,
                    10,
                    str(is_opt_out).upper()
                )

                # Column 11 = reply_snippet
                if snippet:
                    sheet.update_cell(index, 11, snippet[:500])

                logger.info(f"Lead {lead_id} marked as replied")

                return True

            except Exception as error:

                logger.error(f"Failed to update reply status: {error}")

                return False

    logger.warning("Lead not found")

    return False


def mark_unsubscribed(email: str, snippet: str = "") -> bool:
    """
    Finds the LAST (newest) lead row by email and sets opt_out=TRUE,
    replied=TRUE, and stores the reply snippet.
    Returns True if a row was updated, False otherwise.
    """
    try:
        sheet = _get_sheets()
        records = sheet.get_all_records()
        last_row = None
        for i, row in enumerate(records, start=2):
            if row.get("email", "").strip().lower() == email.strip().lower():
                last_row = i
        if last_row:
            sheet.update_cell(last_row, 7, "TRUE")      # column G = replied
            sheet.update_cell(last_row, 10, "TRUE")     # column J = opt_out
            if snippet:
                sheet.update_cell(last_row, 11, snippet[:500])  # column K = reply_snippet
            logger.info(f"Marked {email} as Unsubscribed (opt_out=TRUE) in Sheets")
            return True
        logger.warning(f"Email {email} not found in sheet for unsubscribe")
        return False
    except Exception as e:
        logger.error(f"mark_unsubscribed failed: {e}")
        return False
