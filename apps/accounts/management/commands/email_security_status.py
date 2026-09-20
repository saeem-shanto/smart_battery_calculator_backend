from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.security import email_delivery_error_summary, email_security_available


BREVO_BACKEND = "apps.common.email_backends.BrevoApiEmailBackend"


class Command(BaseCommand):
    help = "Check account-email configuration and optionally send a live test message."

    def add_arguments(self, parser):
        parser.add_argument(
            "--send-to",
            dest="send_to",
            default="",
            help="Optional recipient for a live email-provider test.",
        )

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND
        available = email_security_available()

        self.stdout.write(f"Account email security enabled: {settings.ACCOUNT_EMAIL_ENABLED}")
        self.stdout.write(f"Email backend: {backend}")
        self.stdout.write(f"Default sender: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Frontend URL: {settings.FRONTEND_URL}")

        if backend == BREVO_BACKEND:
            self.stdout.write(
                f"Brevo API key configured: {bool(getattr(settings, 'BREVO_API_KEY', ''))}"
            )
            self.stdout.write(
                f"Brevo sender configured: {bool(getattr(settings, 'BREVO_SENDER_EMAIL', ''))}"
            )
            self.stdout.write(
                f"Brevo sender email: {getattr(settings, 'BREVO_SENDER_EMAIL', '') or '(missing)'}"
            )
            self.stdout.write(
                "Brevo API timeout: "
                f"({getattr(settings, 'BREVO_API_CONNECT_TIMEOUT', 5)}, "
                f"{getattr(settings, 'BREVO_API_READ_TIMEOUT', 15)})"
            )
        elif backend == "django.core.mail.backends.smtp.EmailBackend":
            self.stdout.write(f"SMTP host configured: {bool(getattr(settings, 'EMAIL_HOST', ''))}")
            self.stdout.write(f"SMTP sender configured: {bool(getattr(settings, 'EMAIL_HOST_USER', ''))}")
        else:
            self.stdout.write("Provider-specific credentials are managed by the selected backend.")

        if not available:
            raise CommandError(
                "Email security is not ready. Check ACCOUNT_EMAIL_ENABLED and the selected backend credentials."
            )
        self.stdout.write(self.style.SUCCESS("Email security configuration is ready."))

        recipient = (options.get("send_to") or "").strip()
        if recipient:
            try:
                sent = send_mail(
                    "Smart Battery Calculator email test",
                    "Email-based security is configured correctly through the Brevo API.",
                    settings.DEFAULT_FROM_EMAIL,
                    [recipient],
                )
            except Exception as exc:
                raise CommandError(
                    f"Provider test failed: {email_delivery_error_summary(exc)}"
                ) from exc
            if sent != 1:
                raise CommandError("The email provider did not accept the test message.")
            self.stdout.write(self.style.SUCCESS(f"Test email accepted for {recipient}."))
