import uuid
from django.db import models
from django.utils import timezone

class ProfileUpload(models.Model):
    class Role(models.TextChoices):
        LOAD = "load", "Load"
        PV = "pv", "PV generation"
        COMBINED = "combined", "Combined PV and load"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=12, choices=Role.choices)
    original_name = models.CharField(max_length=255)
    detected_format = models.CharField(max_length=50)
    interval_minutes = models.PositiveSmallIntegerField()
    value_kind = models.CharField(max_length=40, default="energy_kwh_interval")
    parsed_payload = models.JSONField(default=dict)
    warnings = models.JSONField(default=list)
    row_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.original_name} ({self.role})"
