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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Profile for {self.user.get_username()}"


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
