import smtplib
from email.mime.text import MIMEText
from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASS, API_BASE

def send_reset_email(username: str, email: str, token: str):
    link = f"{API_BASE}/reset-password?token={token}"

    msg = MIMEText(f"Hello {username},\n\nClick the link to reset your password:\n{link}\n\nIf not you, ignore this.")
    msg["Subject"] = "RCMP123 Password Reset"
    msg["From"] = SMTP_USER
    msg["To"] = email

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)