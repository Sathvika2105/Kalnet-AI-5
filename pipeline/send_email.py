import smtplib
import time
import logging
import os
import uuid
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

logger = logging.getLogger(__name__)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASS")

DELAY_SECONDS = 30
MAX_RETRIES = 2


def send_email(to, subject, body):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise ValueError(
            "EMAIL_USER and EMAIL_PASS must be set in .env"
        )

    if not to or not subject or not body:
        logger.error(f'Invalid email data: to={to}, subject={subject}')
        return {"success": False, "message": "Invalid email data"}

    email_id = str(uuid.uuid4())
    masked_to = to[:3] + "***" + to[-3:] if len(to) > 6 else "***"

    attempt = 0

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, to, msg.as_string())

            logger.info(f'[{email_id}] Email sent to {masked_to} | Subject: {subject}')
            return {"success": True, "message": "sent"}

        except Exception as e:
            logger.warning(
                f'[{email_id}] Attempt {attempt} failed for {masked_to}: '
                f'{type(e).__name__} - {e}'
            )

            if attempt < MAX_RETRIES:
                time.sleep(DELAY_SECONDS)
            else:
                logger.error(
                    f'[{email_id}] Failed to send email to {masked_to} '
                    f'after {MAX_RETRIES} attempts'
                )
                return {"success": False, "message": f"Failed after {MAX_RETRIES} attempts"}

    return {"success": False, "message": "Unexpected error"}