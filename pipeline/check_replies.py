import imaplib
import email
import email.utils
import os
import sys
import time
import logging
import requests
from datetime import date
from email.header import decode_header
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import sheets
except ImportError:
    print("ERROR: Cannot import sheets.py")
    print("Make sure sheets.py is in the same pipeline/ folder")
    sys.exit(1)

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
load_dotenv(dotenv_path=env_path)

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
RISHAV_PHONE         = os.getenv("RISHAV_PHONE")
ULTRAMSG_INSTANCE_ID = os.getenv("ULTRAMSG_INSTANCE_ID")
ULTRAMSG_TOKEN       = os.getenv("ULTRAMSG_TOKEN")

UNSUBSCRIBE_TRIGGERS = [
    "stop",
    "unsubscribe",
    "remove me",
    "opt out",
    "opt-out",
    "do not contact",
    "please remove",
    "take me off",
    "not interested",
    "don't contact",
]

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'replies.log')),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("check_replies")


def validate_env():
    missing = []
    if not GMAIL_ADDRESS:      missing.append("GMAIL_ADDRESS")
    if not GMAIL_APP_PASSWORD: missing.append("GMAIL_APP_PASSWORD")
    if not RISHAV_PHONE:         missing.append("RISHAV_PHONE")
    if not ULTRAMSG_INSTANCE_ID: missing.append("ULTRAMSG_INSTANCE_ID")
    if not ULTRAMSG_TOKEN:       missing.append("ULTRAMSG_TOKEN")
    if missing:
        print(f"ERROR: Missing in .env file: {', '.join(missing)}")
        print("Fill these in your .env file and try again.")
        sys.exit(1)


def decode_subject(raw_subject: str) -> str:
    if not raw_subject:
        return "(no subject)"
    try:
        parts = decode_header(raw_subject)
        decoded = ""
        for part, enc in parts:
            if isinstance(part, bytes):
                decoded += part.decode(enc or "utf-8", errors="replace")
            else:
                decoded += str(part)
        return decoded.strip()
    except Exception:
        return str(raw_subject)


def extract_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition  = str(part.get("Content-Disposition", ""))
            if content_type == "text/plain" and "attachment" not in disposition:
                charset = part.get_content_charset() or "utf-8"
                try:
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                break
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            raw = msg.get_payload(decode=True)
            body = raw.decode(charset, errors="replace") if raw else ""
        except Exception:
            body = ""
    return " ".join(body.split())[:200]


def is_unsubscribe_request(subject: str, body: str) -> bool:
    combined = (subject + " " + body).lower()
    return any(trigger in combined for trigger in UNSUBSCRIBE_TRIGGERS)


def send_whatsapp_notification(school_name: str, sender_email: str,
                                reply_snippet: str, is_unsub: bool = False) -> bool:
    if is_unsub:
        message = (
            f"STOP RECEIVED — KALNET AI-5\n"
            f"School : {school_name}\n"
            f"Email  : {sender_email}\n"
            f"Action : Marked unsubscribed. No more emails."
        )
    else:
        message = (
            f"REPLY DETECTED — KALNET AI-5\n"
            f"School : {school_name}\n"
            f"Email  : {sender_email}\n"
            f"Preview: {reply_snippet[:100]}"
        )
    try:
        resp = requests.post(
            f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE_ID}/messages/chat",
            json={
                "token": ULTRAMSG_TOKEN,
                "to":    RISHAV_PHONE,
                "body":  message
            },
            timeout=15
        )
        if resp.status_code == 200:
            log.info(f"  WhatsApp sent for: {school_name}")
            return True
        else:
            log.warning(f"  UltraMsg returned {resp.status_code}: {resp.text[:100]}")
            return False
    except requests.exceptions.Timeout:
        log.error("  UltraMsg request timed out")
        return False
    except requests.exceptions.RequestException as e:
        log.error(f"  UltraMsg failed: {e}")
        return False


def connect_to_gmail() -> imaplib.IMAP4_SSL:
    log.info("Connecting to Gmail IMAP (imap.gmail.com:993)...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        log.info("Connected and authenticated")
        return mail
    except imaplib.IMAP4.error as e:
        log.error(f"IMAP login failed: {e}")
        log.error("Fix: Enable IMAP in Gmail settings. Check App Password in .env.")
        raise
    except Exception as e:
        log.error(f"Unexpected Gmail connection error: {e}")
        raise


def build_lead_lookup() -> dict:
    try:
        all_leads = sheets.get_all_leads()
        log.info(f"Loaded {len(all_leads)} leads from Google Sheets")
    except Exception as e:
        log.error(f"Failed to load leads: {e}")
        raise

    lookup = {}
    for lead in all_leads:
        addr         = lead.get("email", "").strip().lower()
        email_sent   = lead.get("email_sent", "").strip().upper()
        reply_recv   = lead.get("reply_received", "").strip().upper()
        unsubscribed = lead.get("unsubscribed", "").strip().upper()
        if addr and email_sent == "Y" and reply_recv != "Y" and unsubscribed != "Y":
            lookup[addr] = lead

    log.info(f"Watching {len(lookup)} emailed leads for replies")
    return lookup


def write_summary_line(unread: int, matched: int, updated: int,
                        wa_sent: int, unsub_count: int):
    summary_path = os.path.join(log_dir, "replies_summary.log")
    line = (
        f"{date.today().isoformat()},"
        f"{unread},{matched},{updated},{wa_sent},{unsub_count}\n"
    )
    try:
        with open(summary_path, "a") as f:
            f.write(line)
        log.info("Summary written to logs/replies_summary.log")
    except Exception as e:
        log.error(f"Could not write summary line: {e}")


def check_for_replies():
    log.info("=" * 60)
    log.info("KALNET AI-5 — Reply Detection Run")
    log.info(f"Date: {date.today().isoformat()}")
    log.info("=" * 60)

    try:
        lead_lookup = build_lead_lookup()
    except Exception:
        log.error("Aborting — could not load leads.")
        return

    if not lead_lookup:
        log.info("No leads awaiting replies. Nothing to do.")
        write_summary_line(0, 0, 0, 0, 0)
        return

    try:
        mail = connect_to_gmail()
    except Exception:
        log.error("Aborting — could not connect to Gmail.")
        return

    total_unread  = 0
    total_matched = 0
    total_updated = 0
    total_wa_sent = 0
    total_unsub   = 0

    try:
        mail.select("INBOX")

        status, data = mail.search(None, "UNSEEN")
        if status != "OK":
            log.warning(f"IMAP search status: {status}")
            return

        msg_ids      = data[0].split()
        total_unread = len(msg_ids)
        log.info(f"Found {total_unread} unread email(s)")

        if not msg_ids:
            log.info("No new emails. Run complete.")
            return

        for msg_id in msg_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")

                if status != "OK" or not msg_data or not msg_data[0]:
                    log.warning(f"Could not fetch message {msg_id} — skipping")
                    continue

                msg = email.message_from_bytes(msg_data[0][1])

                from_header = msg.get("From", "")
                _, sender   = email.utils.parseaddr(from_header)
                sender      = sender.strip().lower()
                subject     = decode_subject(msg.get("Subject", ""))

                log.info(f"Processing: {sender} | {subject}")

                if sender not in lead_lookup:
                    log.info("  Not a tracked lead — skipping")
                    continue

                total_matched += 1
                lead        = lead_lookup[sender]
                lead_id     = lead.get("lead_id") or lead.get("row_number")
                school_name = lead.get("school_name", sender)

                log.info(f"  MATCH: {school_name}")

                snippet = extract_body(msg)
                log.info(f"  Snippet: {snippet[:80]}...")

                if is_unsubscribe_request(subject, snippet):
                    log.info(f"  UNSUBSCRIBE detected for {school_name}")
                    try:
                        sheets.mark_unsubscribed(lead_id)
                        total_updated += 1
                        total_unsub   += 1
                        log.info("  Sheets updated: unsubscribed=Y")
                    except Exception as e:
                        log.error(f"  Failed to mark unsubscribed: {e}")

                    wa_ok = send_whatsapp_notification(
                        school_name, sender, snippet, is_unsub=True
                    )
                    if wa_ok:
                        total_wa_sent += 1

                else:
                    try:
                        sheets.mark_replied(lead_id, snippet)
                        total_updated += 1
                        log.info("  Sheets updated: reply_received=Y")
                    except Exception as e:
                        log.error(f"  Failed to update Sheets: {e}")

                    wa_ok = send_whatsapp_notification(
                        school_name, sender, snippet, is_unsub=False
                    )
                    if wa_ok:
                        total_wa_sent += 1

                del lead_lookup[sender]
                time.sleep(2)

            except Exception as e:
                log.error(f"Error processing message {msg_id}: {e}")
                continue

    finally:
        try:
            mail.logout()
            log.info("IMAP connection closed")
        except Exception:
            pass

    log.info("")
    log.info("-" * 40)
    log.info("RUN SUMMARY")
    log.info(f"  Unread checked  : {total_unread}")
    log.info(f"  Matched to leads: {total_matched}")
    log.info(f"  Sheets updated  : {total_updated}")
    log.info(f"  WhatsApp sent   : {total_wa_sent}")
    log.info(f"  Unsubscribed    : {total_unsub}")
    log.info("-" * 40)

    write_summary_line(
        total_unread, total_matched,
        total_updated, total_wa_sent, total_unsub
    )


if __name__ == "__main__":
    validate_env()
    check_for_replies()

    # To run every hour in a loop instead of cron uncomment below:
    # while True:
    #     validate_env()
    #     check_for_replies()
    #     log.info("Sleeping 1 hour...")
    #     time.sleep(3600)