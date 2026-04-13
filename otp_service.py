import os
import smtplib
import random
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(to_email, otp):
    if not SMTP_EMAIL or not SMTP_APP_PASSWORD:
        raise ValueError("SMTP_EMAIL or SMTP_APP_PASSWORD not set in .env")

    subject = "Your Attendance System OTP"
    body = f"Your OTP is: {otp}\nThis OTP expires in 5 minutes."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())