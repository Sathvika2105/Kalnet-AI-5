from datetime import datetime
import re

USE_MOCK_FOR_DEMO = False


# DEMO / MOCK MODE
if USE_MOCK_FOR_DEMO:

    from config.mock_google_sheets import MockClient as RealClient
    from config.mock_google_sheets import mock_authorize as authorize

    print("Running in DEMO MODE with mock data")

    client = authorize(None)

    sheet = client.open_by_key(
        "1JgAfy93z1Tiqno-suJXKXfP6iLUR3mNzWnATD4TIuSY"
    ).sheet1


# REAL GOOGLE SHEETS MODE
else:

    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "config/service_account.json",
        scope
    )

    client = gspread.authorize(creds)

    sheet = client.open_by_key(
        "1JgAfy93z1Tiqno-suJXKXfP6iLUR3mNzWnATD4TIuSY"
    ).sheet1


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


def clean_lead_data(lead):

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

        "email_sent_at": normalize_date(
            lead.get("email_sent_at", "")
        ),

        "sequence_step": int(
            lead.get("sequence_step", 0) or 0
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
            lead.get("reply_snippet", "")
        ).strip()
    }


# GET ALL LEADS
def get_all_leads():

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


# MARK EMAIL SENT
def mark_email_sent(
    lead_id,
    sequence_step,
    tier="",
    subject_line=""
):

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

                print(f"Updated lead {lead_id}")

                return True

            except Exception as error:

                print(f"Failed to update lead: {error}")

                return False

    print("Lead not found")

    return False


# MARK REPLIED
def mark_replied(
    lead_id,
    snippet=None,
    is_opt_out=False
):

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

                print(f"Lead {lead_id} marked as replied")

                return True

            except Exception as error:

                print(f"Failed to update reply status: {error}")

                return False

    print("Lead not found")

    return False


def mark_unsubscribed(email: str) -> bool:
    """
    Finds the lead row by email and sets opt_out = TRUE in column J (10).
    Returns True on success, False on failure.
    """
    try:
        records = sheet.get_all_records()
        for i, row in enumerate(records, start=2):  # row 1 = header
            if row.get("email", "").strip().lower() == email.strip().lower():
                sheet.update_cell(i, 10, "TRUE")  # column J = opt_out
                print(f"  Marked {email} as Unsubscribed (opt_out=TRUE) in Sheets")
                return True
        print(f"  Email {email} not found in sheet for unsubscribe")
        return False
    except Exception as e:
        print(f"  mark_unsubscribed failed: {e}")
        return False