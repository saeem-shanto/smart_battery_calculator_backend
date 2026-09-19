from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.security import email_security_available


class Command(BaseCommand):
    help = "Check email-security configuration and optionally send a test message."

    def add_arguments(self, parser):
        parser.add_argument("--send-to", dest="send_to", default="", help="Optional recipient for a live SMTP test email.")

    def handle(self, *args, **options):
        available = email_security_available()
        self.stdout.write(f"Account email security enabled: {settings.ACCOUNT_EMAIL_ENABLED}")
        self.stdout.write(f"Email backend: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"SMTP host: {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        self.stdout.write(f"TLS enabled: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"Sender configured: {bool(settings.EMAIL_HOST_USER)}")
        self.stdout.write(f"Frontend URL: {settings.FRONTEND_URL}")
        if not available:
            raise CommandError("Email security is not ready. Check ACCOUNT_EMAIL_ENABLED and SMTP credentials.")
        self.stdout.write(self.style.SUCCESS("Email security configuration is ready."))

        recipient = (options.get("send_to") or "").strip()
        if recipient:
            sent = send_mail(
                "Smart Battery Calculator email test",
                "Email-based security is configured correctly.",
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
            if sent != 1:
                raise CommandError("The SMTP test email was not accepted for delivery.")
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}."))
