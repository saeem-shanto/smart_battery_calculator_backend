from __future__ import annotations

import base64
from email.utils import parseaddr
from typing import Iterable

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage


_DEFAULT_BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def _required_setting(name: str) -> str:
    value = str(getattr(settings, name, "") or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required by the Brevo API email backend.")
    return value


def _timeout() -> tuple[float, float]:
    connect = float(getattr(settings, "BREVO_API_CONNECT_TIMEOUT", 5.0))
    read = float(getattr(settings, "BREVO_API_READ_TIMEOUT", 15.0))
    return (connect, read)


def _mailbox(value: str) -> dict[str, str]:
    name, email = parseaddr(value or "")
    email = email.strip()
    if not email:
        email = (value or "").strip()
    item = {"email": email}
    if name.strip():
        item["name"] = name.strip()
    return item


def _html_alternative(message: EmailMessage) -> str:
    for alternative in getattr(message, "alternatives", ()) or ():
        content = getattr(alternative, "content", None)
        mimetype = getattr(alternative, "mimetype", None)
        if content is None and isinstance(alternative, (tuple, list)) and len(alternative) >= 2:
            content, mimetype = alternative[0], alternative[1]
        if str(mimetype or "").lower() == "text/html":
            return str(content or "")
    if getattr(message, "content_subtype", "plain") == "html":
        return str(message.body or "")
    return ""


def _attachments(message: EmailMessage) -> list[dict[str, str]]:
    """Convert ordinary Django attachments to Brevo base64 attachments.

    Security emails in this project do not attach files, but supporting standard
    byte/string attachments makes this backend safe for other Django callers too.
    Complex MIMEBase attachments are intentionally rejected rather than silently
    mangled.
    """

    result: list[dict[str, str]] = []
    for attachment in getattr(message, "attachments", ()) or ():
        filename = getattr(attachment, "filename", None)
        content = getattr(attachment, "content", None)

        if filename is None and isinstance(attachment, (tuple, list)) and len(attachment) >= 2:
            filename, content = attachment[0], attachment[1]

        if not filename:
            raise ValueError("Brevo API backend cannot send unnamed MIME attachments.")

        if isinstance(content, str):
            raw = content.encode("utf-8")
        elif isinstance(content, (bytes, bytearray, memoryview)):
            raw = bytes(content)
        else:
            raise ValueError(
                f"Unsupported attachment content type for {filename!r}: {type(content).__name__}."
            )

        result.append(
            {
                "name": str(filename),
                "content": base64.b64encode(raw).decode("ascii"),
            }
        )
    return result


class BrevoApiEmailBackend(BaseEmailBackend):
    """Send normal Django EmailMessage objects through Brevo's HTTPS API.

    This intentionally avoids SMTP, so it works on Render Free where outbound
    SMTP ports are restricted. The verified sender configured in Django settings
    is authoritative; callers cannot accidentally substitute an unverified From
    address.
    """

    def send_messages(self, email_messages: Iterable[EmailMessage]) -> int:
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            if not message.recipients():
                continue
            try:
                self._send_message(message)
            except Exception:
                if not self.fail_silently:
                    raise
            else:
                sent_count += 1
        return sent_count

    def _send_message(self, message: EmailMessage) -> None:
        api_key = _required_setting("BREVO_API_KEY")
        sender_email = _required_setting("BREVO_SENDER_EMAIL")
        sender_name = str(
            getattr(settings, "BREVO_SENDER_NAME", "Smart Battery Calculator") or ""
        ).strip()

        recipients = [_mailbox(item) for item in (message.to or [])]
        if not recipients:
            return

        payload: dict[str, object] = {
            "sender": {"email": sender_email, **({"name": sender_name} if sender_name else {})},
            "to": recipients,
            "subject": str(message.subject or ""),
        }

        if message.cc:
            payload["cc"] = [_mailbox(item) for item in message.cc]
        if message.bcc:
            payload["bcc"] = [_mailbox(item) for item in message.bcc]

        reply_to = list(getattr(message, "reply_to", ()) or ())
        configured_reply_to = str(getattr(settings, "BREVO_REPLY_TO_EMAIL", "") or "").strip()
        if reply_to:
            payload["replyTo"] = _mailbox(reply_to[0])
        elif configured_reply_to:
            payload["replyTo"] = _mailbox(configured_reply_to)

        html_body = _html_alternative(message)
        text_body = str(message.body or "")
        if html_body:
            payload["htmlContent"] = html_body
            if text_body and getattr(message, "content_subtype", "plain") != "html":
                payload["textContent"] = text_body
        else:
            payload["textContent"] = text_body or " "

        attachments = _attachments(message)
        if attachments:
            payload["attachment"] = attachments

        send_url = str(
            getattr(settings, "BREVO_API_SEND_URL", _DEFAULT_BREVO_SEND_URL)
            or _DEFAULT_BREVO_SEND_URL
        ).strip()

        response = requests.post(
            send_url,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json",
            },
            json=payload,
            timeout=_timeout(),
        )
        response.raise_for_status()

        # Brevo returns HTTP 201 plus a messageId for successful transactional sends.
        # Be defensive in case a proxy/provider returns an unexpected 2xx body.
        if response.status_code != 201:
            raise RuntimeError(
                f"Brevo API returned unexpected success status {response.status_code}; expected 201."
            )
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError("Brevo API success response was not valid JSON.") from exc
        if not str((body or {}).get("messageId") or "").strip():
            raise RuntimeError("Brevo API success response did not include messageId.")
