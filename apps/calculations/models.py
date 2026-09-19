import uuid

from django.db import models


class StoredInputFile(models.Model):
    """One content-addressed copy of each unique uploaded input payload."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    canonical_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size_bytes = models.PositiveBigIntegerField()
    data = models.BinaryField(editable=False)
    detected_format = models.CharField(max_length=80, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    parsing_warnings = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.canonical_filename} [{self.sha256[:12]}]"


class StoredCsvResult(models.Model):
    """The one canonical legacy CSV generated for a unique input payload.

    source_input_sha256 keeps the content-addressed relationship even when an
    administrator deliberately removes the stored input bytes.
    """

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
    data = models.BinaryField(editable=False)
    result_payload = models.JSONField(default=dict)
    engine_version = models.CharField(max_length=80)
    algorithm_sha256 = models.CharField(max_length=64, blank=True)
    runtime_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.filename} for {self.source_input_sha256[:12]}"


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

    # File rows are intentionally nullable. Administrators can remove input or
    # output bytes without deleting this calculation/audit record.
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

    # Searchable/table-friendly record information.
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
