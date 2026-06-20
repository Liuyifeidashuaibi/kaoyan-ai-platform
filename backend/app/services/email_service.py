"""SMTP email delivery for translator exports."""

from __future__ import annotations

import logging
import smtplib
from email import encoders
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import get_settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def is_email_delivery_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host.strip() and settings.smtp_from.strip())


def send_email_with_attachment(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    attachment_name: str,
    attachment_bytes: bytes,
    attachment_mime: str,
) -> None:
    settings = get_settings()
    if not is_email_delivery_configured():
        raise EmailDeliveryError(
            "Email delivery is not configured on the server (SMTP_HOST / SMTP_FROM)."
        )

    msg = MIMEMultipart()
    msg["From"] = settings.smtp_from.strip()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    main_type, _, sub_type = attachment_mime.partition("/")
    main_type = main_type.strip() or "application"
    sub_type = sub_type.split(";")[0].strip() or "octet-stream"
    part = MIMEApplication(attachment_bytes, _subtype=sub_type)
    part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
    encoders.encode_base64(part)
    msg.attach(part)

    host = settings.smtp_host.strip()
    port = settings.smtp_port
    user = settings.smtp_user.strip()
    password = settings.smtp_password

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if user:
                    server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                if user:
                    server.login(user, password)
                server.send_message(msg)
    except Exception as exc:
        logger.exception("SMTP send failed to %s", to_email)
        raise EmailDeliveryError(f"Failed to send email: {exc}") from exc
