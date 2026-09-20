from __future__ import annotations

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.security import email_delivery_error_summary


class Command(BaseCommand):
    help = "Verify the Brevo API key and configured sender without sending an email."

    def handle(self, *args, **options):
        api_key = str(getattr(settings, "BREVO_API_KEY", "") or "").strip()
        sender_email = str(getattr(settings, "BREVO_SENDER_EMAIL", "") or "").strip().lower()
        if not api_key:
            raise CommandError("BREVO_API_KEY is not configured.")
        if not sender_email:
            raise CommandError("BREVO_SENDER_EMAIL is not configured.")

        timeout = (
            float(getattr(settings, "BREVO_API_CONNECT_TIMEOUT", 5.0)),
            float(getattr(settings, "BREVO_API_READ_TIMEOUT", 15.0)),
        )
        headers = {"accept": "application/json", "api-key": api_key}

        try:
            account = requests.get(
                "https://api.brevo.com/v3/account",
                headers=headers,
                timeout=timeout,
            )
            account.raise_for_status()
            account_payload = account.json()
        except Exception as exc:
            raise CommandError(
                f"Brevo account/API-key check failed: {email_delivery_error_summary(exc)}"
            ) from exc

        self.stdout.write(self.style.SUCCESS("Brevo API key accepted."))
        login = str((account_payload or {}).get("email") or "").strip()
        if login:
            self.stdout.write(f"Brevo account: {login}")

        try:
            response = requests.get(
                "https://api.brevo.com/v3/senders",
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise CommandError(
                f"Brevo sender check failed: {email_delivery_error_summary(exc)}"
            ) from exc

        senders = (payload or {}).get("senders") or []
        match = next(
            (
                item
                for item in senders
                if str((item or {}).get("email") or "").strip().lower() == sender_email
            ),
            None,
        )
        if match is None:
            raise CommandError(
                f"Configured BREVO_SENDER_EMAIL ({sender_email}) is not present in this Brevo account."
            )
        if not bool(match.get("active")):
            raise CommandError(
                f"Configured BREVO_SENDER_EMAIL ({sender_email}) exists but is not active/verified."
            )

        self.stdout.write(
            self.style.SUCCESS(f"Brevo sender is active and ready: {sender_email}")
        )
