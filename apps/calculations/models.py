from __future__ import annotations

import logging
import uuid
from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def input_storage_name(sha256: str) -> str:
    digest = (sha256 or "unknown").lower()
    return f"inputs/{digest[:2]}/{digest}/input.bin"


def csv_storage_name(source_input_sha256: str) -> str:
    digest = (source_input_sha256 or "unknown").lower()
    return f"results/{digest[:2]}/{digest}/Results_RPAtrail400.csv"


def stored_input_upload_to(instance: "StoredInputFile", filename: str) -> str:
    """Deterministic content-addressed key; download filename stays in PostgreSQL."""
    return input_storage_name(instance.sha256)


def stored_csv_upload_to(instance: "StoredCsvResult", filename: str) -> str:
    return csv_storage_name(instance.source_input_sha256)


class StoredInputFile(models.Model):
    """One content-addressed copy of each unique retained input payload.

    New retained files live in the configured Django default storage (Supabase
    Storage in production). ``data`` is a temporary legacy fallback for rows
    created before the Supabase-storage migration and is never populated by
    new v1.5 writes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    canonical_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size_bytes = models.PositiveBigIntegerField()
    storage_file = models.FileField(upload_to=stored_input_upload_to, max_length=500, blank=True)
    data = models.BinaryField(editable=False, null=True, blank=True)
    detected_format = models.CharField(max_length=80, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    parsing_warnings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.canonical_filename} [{self.sha256[:12]}]"

    @property
    def storage_ready(self) -> bool:
        return bool(self.storage_file and self.storage_file.name)


class StoredCsvResult(models.Model):
    """The one canonical legacy CSV generated for a unique input payload."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    input_file = models.OneToOneField(
        StoredInputFile,
        on_delete=models.SET_NULL,
        related_name="csv_result",
        null=True,
        blank=True,
    )
    source_input_sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    filename = models.CharField(max_length=255, default="Results_RPAtrail400.csv")
    content_type = models.CharField(max_length=120, default="text/csv")
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    storage_file = models.FileField(upload_to=stored_csv_upload_to, max_length=500, blank=True)
    data = models.BinaryField(editable=False, null=True, blank=True)
    result_payload = models.JSONField(default=dict)
    engine_version = models.CharField(max_length=80)
    algorithm_sha256 = models.CharField(max_length=64, blank=True)
    runtime_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} for {self.source_input_sha256[:12]}"

    @property
    def storage_ready(self) -> bool:
        return bool(self.storage_file and self.storage_file.name)


class Calculation(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class SourceMode(models.TextChoices):
        UPLOAD = "upload", "Uploaded client workbook"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    access_token_hash = models.CharField(max_length=64, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="battery_calculations",
        null=True,
        blank=True,
        db_index=True,
    )

    input_file = models.ForeignKey(
        StoredInputFile,
        on_delete=models.SET_NULL,
        related_name="calculations",
        null=True,
        blank=True,
    )
    csv_result = models.ForeignKey(
        StoredCsvResult,
        on_delete=models.SET_NULL,
        related_name="calculations",
        null=True,
        blank=True,
    )

    postcode = models.CharField(max_length=12, blank=True, db_index=True)
    suburb = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSING)
    source_mode = models.CharField(max_length=12, choices=SourceMode.choices, default=SourceMode.UPLOAD)
    input_payload = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)
    assumptions = models.JSONField(default=list)
    warnings = models.JSONField(default=list)
    algorithm_version = models.CharField(max_length=80, blank=True)
    runtime_ms = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["postcode", "-created_at"], name="calc_postcode_created_idx"),
            models.Index(fields=["status", "-created_at"], name="calc_status_created_idx"),
        ]

    def __str__(self):
        return str(self.public_id)


def _delete_storage_object_after_commit(instance) -> None:
    field = getattr(instance, "storage_file", None)
    name = getattr(field, "name", "") if field else ""
    if not name:
        return
    storage = field.storage

    def _delete() -> None:
        try:
            storage.delete(name)
        except Exception as exc:  # pragma: no cover - external storage failure
            logger.warning("Could not delete storage object %s: %s", name, type(exc).__name__)

    transaction.on_commit(_delete)


@receiver(post_delete, sender=StoredInputFile)
def delete_input_object(sender, instance, **kwargs):
    _delete_storage_object_after_commit(instance)


@receiver(post_delete, sender=StoredCsvResult)
def delete_csv_object(sender, instance, **kwargs):
    _delete_storage_object_after_commit(instance)


@receiver(post_delete, sender=Calculation)
def cleanup_orphaned_artifacts_after_calculation_delete(sender, instance, **kwargs):
    """Promptly remove private retained artifacts once no calculation needs them.

    Content-addressed objects may be shared by multiple retained calculations, so
    deletion is reference-aware. The cleanup runs after the surrounding database
    transaction commits to avoid removing bytes for a transaction that later rolls back.
    """
    input_id = instance.input_file_id
    csv_id = instance.csv_result_id

    def _cleanup() -> None:
        if csv_id and not Calculation.objects.filter(csv_result_id=csv_id).exists():
            StoredCsvResult.objects.filter(pk=csv_id).delete()
        if input_id:
            still_used = Calculation.objects.filter(input_file_id=input_id).exists()
            csv_uses_input = StoredCsvResult.objects.filter(input_file_id=input_id).exists()
            if not still_used and not csv_uses_input:
                StoredInputFile.objects.filter(pk=input_id).delete()

    transaction.on_commit(_cleanup)
