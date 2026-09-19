from django.core.management.base import BaseCommand
from apps.tariffs.models import TariffPlan

class Command(BaseCommand):
    help = "Seed neutral demonstration tariffs; replace with client-approved tariff data before production."
    def handle(self, *args, **options):
        TariffPlan.objects.update_or_create(
            name="Reference Flat Tariff", provider="Project reference",
            defaults={"kind":"flat", "flat_import_rate":0.3773, "feed_in_rate":0.124, "daily_supply_charge":0, "is_active":True,
                      "notes":"Matches the retail and feed-in rates in the validated client reference algorithm."}
        )
        TariffPlan.objects.update_or_create(
            name="Example Time-of-Use Tariff", provider="Demonstration only",
            defaults={"kind":"tou", "peak_import_rate":0.52, "shoulder_import_rate":0.34, "offpeak_import_rate":0.24,
                      "feed_in_rate":0.08, "daily_supply_charge":1.10, "is_active":True,
                      "notes":"Illustrative values only. Replace with validated tariff data."}
        )
        self.stdout.write(self.style.SUCCESS("Tariffs seeded."))
