import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import UserProfile


class Command(BaseCommand):
    help = "Create or update a staff/superuser account from environment variables."

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "admin").strip()
        email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com").strip()
        first_name = os.getenv("ADMIN_BOOTSTRAP_FIRST_NAME", "").strip()
        last_name = os.getenv("ADMIN_BOOTSTRAP_LAST_NAME", "").strip()
        password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
        if not username:
            raise CommandError("ADMIN_BOOTSTRAP_USERNAME cannot be blank.")
        if not password:
            raise CommandError("Set ADMIN_BOOTSTRAP_PASSWORD before running this command.")

        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username)
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        UserProfile.objects.get_or_create(user=user)
        self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' is ready."))
