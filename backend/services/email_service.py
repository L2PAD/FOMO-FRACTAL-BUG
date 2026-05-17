"""
Email Service — sends transactional emails via SMTP.
Configure via environment variables:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
Falls back to Telegram bot when SMTP is not configured.
"""
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")


def is_smtp_configured() -> bool:
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP. Returns True if sent successfully."""
    if not is_smtp_configured():
        logger.warning("SMTP not configured — cannot send email")
        return False

    try:
        import aiosmtplib

        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_FROM or SMTP_USER
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info(f"Email sent to {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to}: {e}")
        return False


async def send_otp_email(to: str, otp_code: str, new_email: str) -> bool:
    """Send OTP verification email for email change."""
    subject = "FOMO — Код подтверждения смены email"
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 400px; margin: 0 auto; padding: 32px; background: #0d0d0f; color: #ffffff; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #d4ff00; margin: 0;">FOMO</h2>
        </div>
        <p style="color: #a0a0a0; font-size: 14px; margin-bottom: 24px;">
            Вы запросили смену email. Для подтверждения введите код ниже в приложении:
        </p>
        <div style="text-align: center; background: #1a1a1f; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <span style="font-size: 32px; letter-spacing: 8px; font-weight: 700; color: #d4ff00;">{otp_code}</span>
        </div>
        <p style="color: #666; font-size: 12px;">
            Новый email: <strong>{new_email}</strong><br>
            Код действителен 10 минут.<br>
            Если вы не запрашивали смену — проигнорируйте это письмо.
        </p>
    </div>
    """
    return await send_email(to, subject, html)
