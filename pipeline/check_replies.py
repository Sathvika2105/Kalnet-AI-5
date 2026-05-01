"""
Environment variables (put in .env file in project root):
  GMAIL_ADDRESS       = kalnet.outreach@gmail.com
  GMAIL_APP_PASSWORD  = your 16-char Gmail App Password (with spaces is fine)
  RISHAV_PHONE        = +91XXXXXXXXXX
  CALLMEBOT_API_KEY   = your CallMeBot API key
"""

import imaplib
import email
import os
import time
import logging
import requests
from datetime import date
from email.header import decode_header
from dotenv import load_dotenv
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
import sheets

# ──────────────────────────────────────────────
# Load environment variables from .env file
# ──────────────────────────────────────────────
load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RISHAV_PHONE       = os.getenv("RISHAV_PHONE")
CALLMEBOT_API_KEY  = os.getenv("CALLMEBOT_API_KEY")

# ──────────────────────────────────────────────
# Logging setup — logs go to /logs/replies.log
# ──────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/replies.log"),
        logging.StreamHandler()  # also prints to terminal
    ]
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# UTILITY: Decode email subject safely
# ──────────────────────────────────────────────
def decode_subject(raw_subject: str) -> str:
    """Decode email subject that may be encoded (e.g. UTF-8 or base64)."""
    if not raw_subject:
        return "(no subject)"
    parts = decode_header(raw_subject)
    decoded = ""
    for part, encoding in parts:
        if isinstance(part, bytes):
            decoded += part.decode(encoding or "utf-8", errors="replace")
        else:
            decoded += part
    return decoded


# ──────────────────────────────────────────────
# UTILITY: Extract plain text body from email
# ──────────────────────────────────────────────
def extract_body(msg) -> str:
    """
    Extract the plain-text body of an email message.
    Handles multipart emails (text + HTML).
    Returns first 200 characters as required.
    """
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            # We want plain text, not attachments
            if content_type == "text/plain" and "attachment" not in disposition:
                charset = part.get_content_charset() or "utf-8"
                try:
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break  # stop at first plain text part
    else:
        # Single part email
        charset = msg.get_content_charset() or "utf-8"
        try:
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = ""

    # Strip excessive whitespace and return first 200 chars
    body = " ".join(body.split())
    return body[:200]


# ──────────────────────────────────────────────
# WHATSAPP: Send notification via CallMeBot
# ──────────────────────────────────────────────
def send_whatsapp_notification(school_name: str, sender_email: str, reply_snippet: str) -> bool:
    """
    Send a WhatsApp message to Rishav when a reply is detected.
    Uses CallMeBot free API.
    Docs: https://www.callmebot.com/blog/free-api-whatsapp-messages/
    """
    message = (
        f"📩 REPLY DETECTED — KALNET AI-5\n"
        f"School: {school_name}\n"
        f"From: {sender_email}\n"
        f"Preview: {reply_snippet[:100]}..."
    )

    # CallMeBot API endpoint
    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone":  RISHAV_PHONE,
        "text":   message,
        "apikey": CALLMEBOT_API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            log.info(f"WhatsApp notification sent to Rishav for: {school_name}")
            return True
        else:
            log.warning(f"CallMeBot returned status {response.status_code}: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to send WhatsApp notification: {e}")
        return False


# ──────────────────────────────────────────────
# IMAP: Connect to Gmail inbox
# ──────────────────────────────────────────────
def connect_to_gmail() -> imaplib.IMAP4_SSL:
    """
    Connect to Gmail using IMAP over SSL.
    Returns an authenticated IMAP4_SSL connection object.
    """
    log.info("Connecting to Gmail IMAP...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        log.info(" Connected and authenticated to Gmail IMAP")
        return mail
    except imaplib.IMAP4.error as e:
        log.error(f" IMAP login failed: {e}")
        raise


# ──────────────────────────────────────────────
# CORE: Check inbox for new replies
# ──────────────────────────────────────────────
def check_for_replies():
    """
    Main function:
      1. Connects to Gmail via IMAP
      2. Fetches all UNSEEN (unread) emails in INBOX
      3. Matches sender email to leads in Google Sheets
      4. Updates Sheets and sends WhatsApp notification if matched
    """
    log.info("=" * 60)
    log.info("Starting reply detection check...")
    log.info("=" * 60)

    # Step A: Load all current leads from Google Sheets
    # Shreyas's get_all_leads() returns a list of dicts like:
    # [{"lead_id": "...", "email": "...", "school_name": "...", "reply_received": "Y"/"", ...}, ...]
    try:
        all_leads = sheets.get_all_leads()
        log.info(f"Loaded {len(all_leads)} leads from Google Sheets")
    except Exception as e:
        log.error(f" Could not load leads from Google Sheets: {e}")
        return

    # Build a lookup dict: email_address -> lead row
    # Only include leads who have been emailed but NOT yet replied
    lead_lookup = {}
    for lead in all_leads:
        email_addr = lead.get("email", "").strip().lower()
        email_sent = lead.get("email_sent", "").strip().upper()
        reply_received = lead.get("reply_received", "").strip().upper()

        # Only track leads who were emailed and haven't replied yet
        if email_addr and email_sent == "Y" and reply_received != "Y":
            lead_lookup[email_addr] = lead

    log.info(f"🔍 Watching for replies from {len(lead_lookup)} emailed leads")

    if not lead_lookup:
        log.info("No leads to watch for replies. Exiting.")
        return

    # Step B: Connect to Gmail and fetch UNSEEN emails
    try:
        mail = connect_to_gmail()
    except Exception:
        log.error("Aborting — could not connect to Gmail.")
        return

    try:
        mail.select("INBOX")

        # Search for UNSEEN (unread) emails only
        status, message_ids = mail.search(None, "UNSEEN")

        if status != "OK":
            log.warning("IMAP search returned non-OK status.")
            mail.logout()
            return

        id_list = message_ids[0].split()
        log.info(f"📬 Found {len(id_list)} unread email(s) in inbox")

        if not id_list:
            log.info("No new emails. Done.")
            mail.logout()
            return

        # Step C: Process each unread email
        matched_count = 0

        for msg_id in id_list:
            try:
                # Fetch the full email
                status, msg_data = mail.fetch(msg_id, "(RFC822)")

                if status != "OK" or not msg_data or not msg_data[0]:
                    log.warning(f"Skipping message ID {msg_id} — fetch failed")
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract sender's email address
                from_header = msg.get("From", "")
                sender_email = email.utils.parseaddr(from_header)[1].strip().lower()

                subject = decode_subject(msg.get("Subject", ""))
                log.info(f"📧 Processing email from: {sender_email} | Subject: {subject}")

                # Step D: Check if sender matches a lead we're tracking
                if sender_email not in lead_lookup:
                    log.info(f"   Not a tracked lead. Skipping.")
                    continue

                lead = lead_lookup[sender_email]
                lead_id = lead.get("lead_id") or lead.get("row_number")  # depends on Shreyas's implementation
                school_name = lead.get("school_name", sender_email)

                log.info(f" MATCH FOUND: {school_name} ({sender_email})")

                # Extract reply snippet (first 200 chars of body)
                reply_snippet = extract_body(msg)
                log.info(f"   Reply preview: {reply_snippet[:80]}...")

                # Step E: Update Google Sheets via Shreyas's module
                today_str = date.today().isoformat()  # e.g. "2026-04-25"
                try:
                    sheets.mark_replied(lead_id, reply_snippet)
                    log.info(f"   ✅ Sheets updated: reply_received=Y, reply_date={today_str}")
                except Exception as e:
                    log.error(f"   ❌ Failed to update Sheets for {school_name}: {e}")
                    # Still try to send WhatsApp even if Sheets fails

                # Step F: Send WhatsApp notification to Rishav
                send_whatsapp_notification(school_name, sender_email, reply_snippet)

                matched_count += 1

                # Remove from lookup so we don't process duplicates in same run
                del lead_lookup[sender_email]

                # Small delay between processing emails — be kind to APIs
                time.sleep(2)

            except Exception as e:
                log.error(f"❌ Error processing message {msg_id}: {e}")
                continue

        log.info(f"\n📊 Summary: {matched_count} matched reply(ies) processed out of {len(id_list)} new email(s)")

    finally:
        # Always logout cleanly
        try:
            mail.logout()
            log.info("IMAP connection closed.")
        except Exception:
            pass


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    """
    Run this script directly:
        python pipeline/check_replies.py

    Or schedule it to run every hour using cron:
        crontab -e
        0 * * * * cd /path/to/kalnet-ai-5 && python pipeline/check_replies.py

    Or use the scheduler below to loop every hour within one process.
    Uncomment the loop below if you want it to run continuously.
    """

    # Option A: Run once (recommended for cron scheduling)
    check_for_replies()

    # Option B: Run every hour in a loop (uncomment if not using cron)
    # while True:
    #     check_for_replies()
    #     log.info("Sleeping for 1 hour before next check...")
    #     time.sleep(3600)  # 3600 seconds = 1 hour