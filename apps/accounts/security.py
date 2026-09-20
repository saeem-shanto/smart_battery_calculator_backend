from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.html import escape
from django.utils.http import urlsafe_base64_encode

from .models import TwoFactorChallenge, UserProfile

User = get_user_model()


class EmailSecurityUnavailable(RuntimeError):
    pass


class EmailDeliveryFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    expires_in: int
    resend_after: int
    masked_email: str
    purpose: str


def email_security_available() -> bool:
    if not getattr(settings, "ACCOUNT_EMAIL_ENABLED", False):
        return False
    backend = getattr(settings, "EMAIL_BACKEND", "")
    if backend.endswith("console.EmailBackend"):
        return True
    return bool(getattr(settings, "EMAIL_HOST_USER", "") and getattr(settings, "EMAIL_HOST_PASSWORD", ""))


def mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return "configured email address"
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        local_masked = "*"
    elif len(local) == 2:
        local_masked = f"{local[0]}*"
    else:
        local_masked = f"{local[0]}{'*' * min(5, len(local) - 2)}{local[-1]}"
    return f"{local_masked}@{domain}"


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_user_email_verified(user, profile: UserProfile | None = None) -> bool:
    current_email = normalize_email(getattr(user, "email", ""))
    if not current_email:
        return False
    if profile is None:
        try:
            profile = user.battery_profile
        except UserProfile.DoesNotExist:
            return False
    return normalize_email(profile.verified_email) == current_email


def _otp_digest(challenge_id: str, code: str) -> str:
    payload = f"{challenge_id}:{code}".encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_email(subject: str, to_email: str, text_body: str, html_body: str) -> None:
    if not email_security_available():
        raise EmailSecurityUnavailable("Email security features are not configured.")
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    try:
        sent = message.send(fail_silently=False)
    except Exception as exc:  # external SMTP failure
        raise EmailDeliveryFailed("The security email could not be sent.") from exc
    if sent != 1:
        raise EmailDeliveryFailed("The security email could not be sent.")


def _otp_email(user, code: str, purpose: str) -> tuple[str, str, str]:
    minutes = max(1, int(getattr(settings, "TWO_FACTOR_OTP_TTL_SECONDS", 600) / 60))
    display_name = user.get_full_name().strip() or user.get_username()
    html_name = escape(display_name)
    if purpose == TwoFactorChallenge.Purpose.ENABLE:
        subject = "Confirm two-factor authentication"
        action = "confirm two-factor authentication for your Smart Battery Calculator account"
    elif purpose == TwoFactorChallenge.Purpose.VERIFY_EMAIL:
        subject = "Verify your Smart Battery Calculator email"
        action = "verify this email address for your Smart Battery Calculator account"
    else:
        subject = "Your Smart Battery Calculator sign-in code"
        action = "complete your Smart Battery Calculator sign-in"
    text = (
        f"Hello {display_name},\n\n"
        f"Use this one-time code to {action}:\n\n"
        f"{code}\n\n"
        f"This code expires in {minutes} minutes and can only be used once. "
        "If you did not request this, you can ignore this email.\n\n"
        "Smart Battery Calculator"
    )
    html = (
        f"<p>Hello {html_name},</p>"
        f"<p>Use this one-time code to {action}:</p>"
        f"<p style='font-size:28px;font-weight:700;letter-spacing:6px'>{code}</p>"
        f"<p>This code expires in {minutes} minutes and can only be used once.</p>"
        "<p>If you did not request this, you can ignore this email.</p>"
        "<p>Smart Battery Calculator</p>"
    )
    return subject, text, html


def create_two_factor_challenge(user, purpose: str) -> ChallengeResult:
    target_email = normalize_email(user.email)
    if not target_email:
        raise EmailSecurityUnavailable("An email address is required for this email-security action.")
    if not email_security_available():
        raise EmailSecurityUnavailable("Email security features are not configured.")

    now = timezone.now()
    ttl_seconds = int(getattr(settings, "TWO_FACTOR_OTP_TTL_SECONDS", 600))
    resend_after = int(getattr(settings, "TWO_FACTOR_OTP_RESEND_SECONDS", 60))
    code = _new_code()

    with transaction.atomic():
        TwoFactorChallenge.objects.select_for_update().filter(
            user=user,
            purpose=purpose,
            consumed_at__isnull=True,
        ).update(consumed_at=now)
        challenge = TwoFactorChallenge.objects.create(
            user=user,
            purpose=purpose,
            target_email=target_email,
            expires_at=now + timedelta(seconds=ttl_seconds),
            last_sent_at=now,
        )
        challenge.code_digest = _otp_digest(str(challenge.id), code)
        challenge.save(update_fields=["code_digest"])

    subject, text, html = _otp_email(user, code, purpose)
    try:
        _send_email(subject, target_email, text, html)
    except Exception:
        TwoFactorChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        raise

    return ChallengeResult(
        challenge_id=str(challenge.id),
        expires_in=ttl_seconds,
        resend_after=resend_after,
        masked_email=mask_email(target_email),
        purpose=purpose,
    )


def resend_two_factor_challenge(challenge_id: str) -> ChallengeResult:
    now = timezone.now()
    ttl_seconds = int(getattr(settings, "TWO_FACTOR_OTP_TTL_SECONDS", 600))
    resend_after = int(getattr(settings, "TWO_FACTOR_OTP_RESEND_SECONDS", 60))

    with transaction.atomic():
        challenge = TwoFactorChallenge.objects.select_for_update().select_related("user").get(pk=challenge_id)
        if challenge.consumed_at is not None or challenge.expires_at <= now:
            raise ValueError("This verification challenge has expired. Please sign in again.")
        elapsed = (now - challenge.last_sent_at).total_seconds()
        if elapsed < resend_after:
            wait = max(1, int(resend_after - elapsed))
            raise RuntimeError(f"Please wait {wait} seconds before requesting another code.")
        code = _new_code()
        challenge.code_digest = _otp_digest(str(challenge.id), code)
        challenge.expires_at = now + timedelta(seconds=ttl_seconds)
        challenge.last_sent_at = now
        challenge.attempts = 0
        challenge.save(update_fields=["code_digest", "expires_at", "last_sent_at", "attempts"])

    target_email = normalize_email(challenge.target_email or challenge.user.email)
    if not target_email:
        TwoFactorChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        raise EmailSecurityUnavailable("The email address for this verification challenge is no longer available.")
    subject, text, html = _otp_email(challenge.user, code, challenge.purpose)
    try:
        _send_email(subject, target_email, text, html)
    except Exception:
        TwoFactorChallenge.objects.filter(pk=challenge.pk).update(consumed_at=timezone.now())
        raise
    return ChallengeResult(
        challenge_id=str(challenge.id),
        expires_in=ttl_seconds,
        resend_after=resend_after,
        masked_email=mask_email(target_email),
        purpose=challenge.purpose,
    )


def verify_two_factor_challenge(challenge_id: str, code: str, allowed_purposes: set[str] | None = None):
    now = timezone.now()
    max_attempts = int(getattr(settings, "TWO_FACTOR_OTP_MAX_ATTEMPTS", 5))
    with transaction.atomic():
        challenge = TwoFactorChallenge.objects.select_for_update().select_related("user").get(pk=challenge_id)
        if allowed_purposes and challenge.purpose not in allowed_purposes:
            raise ValueError("This verification challenge is not valid for this action.")
        if challenge.consumed_at is not None:
            raise ValueError("This verification code has already been used.")
        if challenge.expires_at <= now:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            raise ValueError("This verification code has expired. Please request a new one.")
        if challenge.attempts >= max_attempts:
            challenge.consumed_at = now
            challenge.save(update_fields=["consumed_at"])
            raise ValueError("Too many incorrect attempts. Please sign in again.")

        expected = _otp_digest(str(challenge.id), code.strip())
        if not hmac.compare_digest(challenge.code_digest, expected):
            challenge.attempts += 1
            if challenge.attempts >= max_attempts:
                challenge.consumed_at = now
                challenge.save(update_fields=["attempts", "consumed_at"])
            else:
                challenge.save(update_fields=["attempts"])
            remaining = max(0, max_attempts - challenge.attempts)
            raise PermissionError(f"Incorrect verification code. {remaining} attempt(s) remaining.")

        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        return challenge


def build_password_reset_url(user) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    query = urlencode({"uid": uid, "token": token})
    return f"{settings.FRONTEND_URL.rstrip('/')}/account/reset-password?{query}"


def send_password_reset_email(user) -> None:
    if not user.email:
        return
    url = build_password_reset_url(user)
    html_url = escape(url)
    display_name = user.get_full_name().strip() or user.get_username()
    html_name = escape(display_name)
    minutes = max(1, int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600) / 60))
    subject = "Reset your Smart Battery Calculator password"
    text = (
        f"Hello {display_name},\n\n"
        "We received a request to reset your Smart Battery Calculator password.\n\n"
        f"Open this link to choose a new password:\n{url}\n\n"
        f"This link expires in approximately {minutes} minutes and becomes invalid after your password changes.\n"
        "If you did not request a password reset, you can ignore this email."
    )
    html = (
        f"<p>Hello {html_name},</p>"
        "<p>We received a request to reset your Smart Battery Calculator password.</p>"
        f"<p><a href='{html_url}'>Reset your password</a></p>"
        f"<p>This link expires in approximately {minutes} minutes and becomes invalid after your password changes.</p>"
        "<p>If you did not request a password reset, you can ignore this email.</p>"
    )
    _send_email(subject, user.email, text, html)
