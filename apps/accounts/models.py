from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import get_valid_filename

logger = logging.getLogger(__name__)


def user_avatar_upload_to(instance: "UserProfile", filename: str) -> str:
    suffix = Path(filename or "avatar.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    safe_stem = get_valid_filename(Path(filename or "avatar").stem)[:50] or "avatar"
    return f"profiles/{instance.user_id}/avatars/{uuid.uuid4().hex}_{safe_stem}{suffix}"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="battery_profile",
    )
    avatar = models.ImageField(upload_to=user_avatar_upload_to, max_length=500, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    verified_email = models.EmailField(max_length=254, blank=True, default="")
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.get_username()}"


class TwoFactorChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN_USER = "login_user", "User login"
        LOGIN_ADMIN = "login_admin", "Admin login"
        ENABLE = "enable", "Enable two-factor authentication"
        VERIFY_EMAIL = "verify_email", "Verify account email"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="two_factor_challenges",
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    target_email = models.EmailField(max_length=254, blank=True, default="")
    code_digest = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose", "consumed_at"], name="accounts_tw_user_id_322cc0_idx"),
            models.Index(fields=["expires_at"], name="accounts_tw_expires_e094f8_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.purpose} challenge for {self.user_id}"


class SecurityEmailCooldown(models.Model):
    """Privacy-preserving cooldown state for public email-security endpoints.

    Only an HMAC digest of the normalized target address is stored, never the
    submitted email itself. This lets password-reset requests apply the same
    cooldown to existing and non-existing accounts without enabling account
    enumeration through response timing/status differences.
    """

    class Action(models.TextChoices):
        PASSWORD_RESET = "password_reset", "Password reset"

    action = models.CharField(max_length=32, choices=Action.choices)
    target_hash = models.CharField(max_length=64)
    last_requested_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["action", "target_hash"],
                name="accounts_sec_email_unique",
            )
        ]
        indexes = [
            models.Index(fields=["updated_at"], name="accounts_sec_email_updated_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} cooldown {self.target_hash[:8]}…"


def _delete_storage_name(field, name: str) -> None:
    if not name:
        return
    storage = field.storage

    def _delete() -> None:
        try:
            storage.delete(name)
        except Exception as exc:  # pragma: no cover - external storage failure
            logger.warning("Could not delete avatar object %s: %s", name, type(exc).__name__)

    transaction.on_commit(_delete)


@receiver(pre_save, sender=UserProfile)
def remember_previous_avatar(sender, instance: UserProfile, **kwargs):
    if not instance.pk:
        instance._previous_avatar_name = ""
        return
    try:
        previous = sender.objects.only("avatar").get(pk=instance.pk)
        instance._previous_avatar_name = previous.avatar.name if previous.avatar else ""
    except sender.DoesNotExist:
        instance._previous_avatar_name = ""


@receiver(post_save, sender=UserProfile)
def delete_replaced_avatar(sender, instance: UserProfile, **kwargs):
    previous_name = getattr(instance, "_previous_avatar_name", "")
    current_name = instance.avatar.name if instance.avatar else ""
    if previous_name and previous_name != current_name:
        _delete_storage_name(instance.avatar, previous_name)


@receiver(post_delete, sender=UserProfile)
def delete_profile_avatar(sender, instance: UserProfile, **kwargs):
    if instance.avatar and instance.avatar.name:
        _delete_storage_name(instance.avatar, instance.avatar.name)
