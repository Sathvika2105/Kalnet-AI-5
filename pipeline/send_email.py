import smtplib
import time
import logging
import os
import uuid
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

logging.basicConfig(
    filename='email_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Use .env for sender email and password
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("EMAIL_USER")
SENDER_PASSWORD = os.getenv("EMAIL_PASS")

DELAY_SECONDS = 30
MAX_RETRIES = 2  # 1 initial attempt + 1 retry


def send_email(to, subject, body):
    # Input validation
    if not to or not subject or not body:
        logging.error(f'Invalid email data: to={to}, subject={subject}')
        return False

    # Unique ID for tracking
    email_id = str(uuid.uuid4())

    # Mask email for safer logs
    masked_to = to[:3] + "***" + to[-3:] if len(to) > 6 else "***"

    attempt = 0

    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            # Connect & send
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, to, msg.as_string())

            logging.info(f'[{email_id}] Email sent to {masked_to} | Subject: {subject}')
            return True

        except Exception as e:
            logging.warning(
                f'[{email_id}] Attempt {attempt} failed for {masked_to}: '
                f'{type(e).__name__} - {e}'
            )

            if attempt < MAX_RETRIES:
                time.sleep(DELAY_SECONDS)
            else:
                logging.error(
                    f'[{email_id}] Failed to send email to {masked_to} '
                    f'after {MAX_RETRIES} attempts'
                )
                return False

    return False
send_email("ajith1731715@gmail.com", "Test Email from Kalnet", "This is a test email sent from the Kalnet.")