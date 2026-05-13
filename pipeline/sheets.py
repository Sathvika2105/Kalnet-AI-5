import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime


scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]


creds = ServiceAccountCredentials.from_json_keyfile_name(
    "config/service_account.json",
    scope
)


client = gspread.authorize(creds)

sheet = client.open("Test_Emails_KALNET").sheet1


def clean_lead_data(lead):

    return {
        "lead_id": str(lead["lead_id"]).strip(),
        "name": str(lead["name"]).strip(),
        "email": str(lead["email"]).strip(),
        "company": str(lead["company"]).strip(),
        "email_sent_at": str(lead["email_sent_at"]).strip(),
        "sequence_step": int(lead["sequence_step"]),
        "replied": str(lead["replied"]).strip().upper() == "TRUE"
    }


def get_all_leads():

    records = sheet.get_all_records()

    leads = []

    for row in records:

        lead = {
            "lead_id": row["lead_id"],
            "name": row["name"],
            "email": row["email"],
            "company": row["company"],
            "email_sent_at": row["email_sent_at"],
            "sequence_step": row["sequence_step"],
            "replied": row["replied"]
        }

        leads.append(clean_lead_data(lead))

    return leads


def get_pending_leads():

    leads = get_all_leads()

    pending = []

    for lead in leads:

        if not lead["replied"]:

            pending.append(lead)

    return pending


def get_lead_by_id(lead_id):

    leads = get_all_leads()

    for lead in leads:

        if str(lead["lead_id"]) == str(lead_id):

            return lead

    return None


def mark_email_sent(lead_id, sequence_step):

    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):

        if str(row["lead_id"]) == str(lead_id):

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sheet.update_cell(index, 5, current_time)

            sheet.update_cell(index, 7, sequence_step)

            print(f"Updated lead {lead_id}")

            return

    print("Lead not found")


def mark_replied(lead_id):

    records = sheet.get_all_records()

    for index, row in enumerate(records, start=2):

        if str(row["lead_id"]) == str(lead_id):

            sheet.update_cell(index, 8, "TRUE")

            print(f"Lead {lead_id} marked as replied")

            return

    print("Lead not found")
