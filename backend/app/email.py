"""Email sending via the Resend HTTP API.

Uses only the standard library (urllib) so the serverless function needs no
extra dependency. Degrades gracefully: if RESEND_API_KEY isn't set, messages are
logged instead of sent, so local dev and the test suite never block on email.
All sending is best-effort — callers use :func:`try_send`, which never raises,
so a mail failure can't break the request that triggered it.
"""
import json
import logging
import urllib.request

from .config import settings

logger = logging.getLogger("app.email")

RESEND_ENDPOINT = "https://api.resend.com/emails"


def email_enabled() -> bool:
    return bool(settings.RESEND_API_KEY)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send one plain-text email via Resend. Returns True if actually sent."""
    if not email_enabled():
        logger.info("[email disabled] to=%s subject=%s\n%s", to, subject, body)
        return False

    payload = json.dumps({
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode()

    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
    logger.info("Sent email to %s: %s", to, subject)
    return True


def try_send(to: str, subject: str, body: str) -> bool:
    """Send but swallow all errors (logged). Never raises."""
    try:
        return send_email(to, subject, body)
    except Exception:  # pragma: no cover - network/API failures
        logger.exception("Failed to send email to %s (%s)", to, subject)
        return False
