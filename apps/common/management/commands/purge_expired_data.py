from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import TwoFactorChallenge
from apps.calculations.models import Calculation, StoredCsvResult, StoredInputFile
from apps.profiles.models import ProfileUpload


class Command(BaseCommand):
    help = "Delete expired staged profiles, old calculations, and unreferenced stored input/CSV files."

    def handle(self, *args, **options):
        now = timezone.now()
        profile_qs = ProfileUpload.objects.filter(expires_at__lte=now)
        profile_count = profile_qs.count()
        profile_qs.delete()

        cutoff = now - timedelta(days=settings.CALCULATION_RETENTION_DAYS)
        calculation_qs = Calculation.objects.filter(created_at__lt=cutoff)
        calculation_count = calculation_qs.count()
        calculation_qs.delete()

        orphan_csv_qs = StoredCsvResult.objects.filter(calculations__isnull=True)
        orphan_csv_count = orphan_csv_qs.count()
        orphan_csv_qs.delete()

        orphan_input_qs = StoredInputFile.objects.filter(
            calculations__isnull=True,
            csv_result__isnull=True,
        )
        orphan_input_count = orphan_input_qs.count()
        orphan_input_qs.delete()

        security_cutoff = now - timedelta(days=1)
        challenge_qs = TwoFactorChallenge.objects.filter(expires_at__lt=security_cutoff)
        challenge_count = challenge_qs.count()
        challenge_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Purged {profile_count} expired profile records, {calculation_count} old calculation records, "
                f"{orphan_input_count} unreferenced input files, {orphan_csv_count} unreferenced CSV files, "
                f"and {challenge_count} expired 2FA challenge records."
            )
        )
