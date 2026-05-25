import os
from dotenv import load_dotenv

load_dotenv()
email_user = os.getenv("EMAIL_USER")
email_pass = os.getenv("EMAIL_PASS")

print(f"EMAIL_USER: {email_user}")
print(f"EMAIL_PASS present: {'Yes' if email_pass else 'No'}")
print(f"EMAIL_PASS length: {len(email_pass) if email_pass else 0}")

# Test SMTP connection
import smtplib

try:
    server = smtplib.SMTP('smtp.gmail.com', 587, timeout=5)
    print("SMTP connection successful")
    server.starttls()
    print("STARTTLS successful")
    server.login(email_user, email_pass)
    print("Login successful!")
except Exception as e:
    print(f"Error: {type(e).__name__} - {e}")
finally:
    try:
        server.quit()
    except:
        pass
