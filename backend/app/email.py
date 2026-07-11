"""Email sending via Gmail SMTP.

Degrades gracefully: if SMTP isn't configured (no user/password), messages are
logged instead of sent, so local dev and the test suite never block on email.
All sending is best-effort — callers use :func:`try_send`, which never raises,
so a mail failure can't break the request that triggered it.
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage

from .config import settings

logger = logging.getLogger("app.email")


def email_enabled() -> bool:
    return bool(settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send one plain-text email. Returns True if actually sent."""
    if not email_enabled():
        logger.info("[email disabled] to=%s subject=%s\n%s", to, subject, body)
        return False

    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        server.starttls(context=context)
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    logger.info("Sent email to %s: %s", to, subject)
    return True


def try_send(to: str, subject: str, body: str) -> bool:
    """Send but swallow all errors (logged). Never raises."""
    try:
        return send_email(to, subject, body)
    except Exception:  # pragma: no cover - network/SMTP failures
        logger.exception("Failed to send email to %s (%s)", to, subject)
        return False
