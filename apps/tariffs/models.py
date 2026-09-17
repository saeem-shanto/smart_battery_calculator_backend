import uuid
from django.db import models

class TariffPlan(models.Model):
    class Kind(models.TextChoices):
        FLAT = "flat", "Flat"
        TOU = "tou", "Time of use"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    provider = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.FLAT)
    flat_import_rate = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    peak_import_rate = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    shoulder_import_rate = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    offpeak_import_rate = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    feed_in_rate = models.DecimalField(max_digits=8, decimal_places=5, default=0)
    daily_supply_charge = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    demand_charge_rate_per_kw_day = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    peak_start_hour = models.PositiveSmallIntegerField(default=16)
    peak_end_hour = models.PositiveSmallIntegerField(default=21)
    shoulder_start_hour = models.PositiveSmallIntegerField(default=7)
    shoulder_end_hour = models.PositiveSmallIntegerField(default=23)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["provider", "name"]

    def __str__(self):
        return f"{self.provider + ' - ' if self.provider else ''}{self.name}"
