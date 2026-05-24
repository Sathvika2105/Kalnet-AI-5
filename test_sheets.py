import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("config/service_account.json", scope)
client = gspread.authorize(creds)

sheet = client.open("Test_Emails_KALNET").sheet1
print(sheet.get_all_records())
