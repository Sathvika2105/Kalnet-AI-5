import base64
import logging
import os
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("EMAIL_USER")

# ── Build Gmail API service ───────────────────────────────────────────────────
def _get_gmail_service():
    """Build Gmail API service using OAuth2 credentials from env."""
    client_id     = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    token         = os.getenv("GMAIL_TOKEN")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("Missing Gmail OAuth credentials in environment variables")

    creds = Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/gmail.send"]
    )
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_message(to, subject, body):
    """Create base64 encoded email message."""
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


# ── Main send function ────────────────────────────────────────────────────────
def send_email(to, subject, body):
    if not SENDER_EMAIL:
        raise ValueError("EMAIL_USER must be set in .env")

    if not to or not subject or not body:
        logger.error(f'Invalid email data: to={to}, subject={subject}')
        return {"success": False, "message": "Invalid email data"}

    email_id = str(uuid.uuid4())
    masked_to = to[:3] + "***" + to[-3:] if len(to) > 6 else "***"

    try:
        service = _get_gmail_service()
        message = _build_message(to, subject, body)
        service.users().messages().send(userId="me", body=message).execute()
        logger.info(f'[{email_id}] Email sent to {masked_to} | Subject: {subject}')
        return {"success": True, "message": "sent"}

    except HttpError as e:
        logger.error(f'[{email_id}] Gmail API error for {masked_to}: {e}')
        return {"success": False, "message": str(e)}

    except Exception as e:
        logger.error(f'[{email_id}] Failed to send email to {masked_to}: {type(e).__name__} - {e}')
        return {"success": False, "message": str(e)}
