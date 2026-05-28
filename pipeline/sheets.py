from datetime import datetime

USE_MOCK_FOR_DEMO = False

# DEMO / MOCK MODE 
if USE_MOCK_FOR_DEMO:

    from config.mock_google_sheets import MockClient as RealClient
    from config.mock_google_sheets import mock_authorize as authorize

    print("Running in DEMO MODE with mock data")

    client = authorize(None)

    # sheet = client.open("Test_Emails_KALNET").sheet1
    sheet = client.open_by_key("1JgAfy93z1Tiqno-suJXKXfP6iLUR3mNzWnATD4TIuSY").sheet1


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

    # sheet = client.open("Test_Emails_KALNET").sheet1
    sheet = client.open_by_key("1JgAfy93z1Tiqno-suJXKXfP6iLUR3mNzWnATD4TIuSY").sheet1


# CLEAN LEAD DATA
def clean_lead_data(lead):

    return {
        "lead_id": str(lead.get("lead_id", "")).strip(),

        "name": str(lead.get("name", "")).strip(),

        "email": str(lead.get("email", "")).strip(),

        "company": str(lead.get("company", "")).strip(),

        # "email_sent_at": str(
        #     lead.get("email_sent_at", "")
        # ).strip(),

        "email_sent_at": str(lead.get("email_sent_at", "")).strip().split(" ")[0].split("T")[0],

        "sequence_step": int(
            lead.get("sequence_step", 0) or 0
        ),

        "replied": str(
            lead.get("replied", "")
        ).strip().upper() == "TRUE"
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

        if not lead["replied"]:

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
def mark_email_sent(lead_id, sequence_step):

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

                print(f"Updated lead {lead_id}")

                return True

            except Exception as error:

                print(f"Failed to update lead: {error}")

                return False

    print("Lead not found")

    return False


# MARK REPLIED
def mark_replied(lead_id, snippet=None):

    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):

        if str(row.get("lead_id", "")) == str(lead_id):

            try:

                # Column 7 = replied
                sheet.update_cell(index, 7, "TRUE")

                print(f"Lead {lead_id} marked as replied")

                return True

            except Exception as error:

                print(f"Failed to update reply status: {error}")

                return False

    print("Lead not found")

    return False
