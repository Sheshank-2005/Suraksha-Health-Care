import os
import sys
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

to = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PATIENTCARE_SMTP_USER", "")
host = os.environ.get("PATIENTCARE_SMTP_HOST", "").strip()
port = int(os.environ.get("PATIENTCARE_SMTP_PORT", "587"))
security = os.environ.get("PATIENTCARE_SMTP_SECURITY", "starttls").strip().lower()
user = os.environ.get("PATIENTCARE_SMTP_USER", "").strip()
password = os.environ.get("PATIENTCARE_SMTP_PASSWORD", "").strip()
sender = os.environ.get("PATIENTCARE_SMTP_FROM", user).strip()

if not to:
    raise SystemExit("Usage: python test_email.py your-email@example.com")
if not all([host, user, password, sender]):
    raise SystemExit("SMTP is not fully configured. Check your .env file.")

msg = EmailMessage()
msg["Subject"] = "Suraksha Health Care SMTP test"
msg["From"] = sender
msg["To"] = to
msg.set_content("This is a test email from the PRJ_279 Suraksha Health Care password-reset configuration.")

try:
    if security in ("ssl", "smtps") or port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            if security in ("starttls", "tls"):
                server.starttls()
                server.ehlo()
            server.login(user, password)
            server.send_message(msg)
    print(f"SUCCESS: test email sent to {to}")
except smtplib.SMTPAuthenticationError:
    print("ERROR: SMTP authentication failed. For Gmail, use a Google App Password, not your normal Gmail password.")
    raise SystemExit(1)
except Exception as exc:
    print(f"ERROR: {type(exc).__name__}: {exc}")
    raise SystemExit(1)
