from rest_framework import serializers
from .models import TariffPlan

class TariffPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = TariffPlan
        fields = [
            "id", "name", "provider", "kind", "flat_import_rate", "peak_import_rate",
            "shoulder_import_rate", "offpeak_import_rate", "feed_in_rate", "daily_supply_charge",
            "demand_charge_rate_per_kw_day", "peak_start_hour", "peak_end_hour",
            "shoulder_start_hour", "shoulder_end_hour", "notes"
        ]
