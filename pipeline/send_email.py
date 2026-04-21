import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logging.basicConfig(
    filename='email_log.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'KALNET mail'
SENDER_PASSWORD = 'App password'
DELAY_SECONDS = 30


def send_email(to, subject, body):
    max_retries = 2
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to, msg.as_string())
            server.quit()

            logging.info(f'Email sent successfully to {to} | Subject: {subject}')
            return True

        except Exception as e:
            logging.warning(f'Attempt {attempt} failed for {to}: {e}')
            if attempt < max_retries:
                time.sleep(DELAY_SECONDS)
            else:
                logging.error(f'Failed to send email to {to} after {max_retries} attempts')
                return False

    return False
