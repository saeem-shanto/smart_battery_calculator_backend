from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.profiles.models import ProfileUpload


class Command(BaseCommand):
    help = "Delete expired parsed upload data. No raw files are retained by the API."

    def handle(self, *args, **options):
        deleted, _ = ProfileUpload.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired upload records."))
