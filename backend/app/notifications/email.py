"""Email channel: send via SMTP. Requires SMTP host + auth + recipients."""
from __future__ import annotations

import logging
import smtplib
from email.mime.text import MIMEText

from .. import config

logger = logging.getLogger(__name__)


def send(message: str, subject: str = "", **kwargs) -> bool:
    if not (config.SMTP_HOST and config.EMAIL_RECIPIENTS):
        logger.debug("Email not configured or no recipients — skipping.")
        return False
    sender = config.SMTP_FROM or (config.SMTP_USER or "ident-scan@local")
    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = subject or "IDENT-SCAN alert"
        msg["From"] = sender
        msg["To"] = ", ".join(config.EMAIL_RECIPIENTS)

        import ssl

        if config.SMTP_PORT == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as server:
                server.set_debuglevel(0)
                if config.SMTP_USER:
                    server.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
                server.sendmail(sender, config.EMAIL_RECIPIENTS, msg.as_string())
                return True

        # Starttls (ports 25/587) or plain.
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        server.ehlo()
        try:
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD or "")
            server.sendmail(sender, config.EMAIL_RECIPIENTS, msg.as_string())
        finally:
            server.quit()
        return True
    except Exception as exc:
        logger.warning("Email send failed: %s", exc)
        return False