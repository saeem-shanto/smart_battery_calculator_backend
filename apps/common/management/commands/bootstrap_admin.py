import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Create or update the development/admin user from environment variables."
    def handle(self, *args, **options):
        username = os.getenv("ADMIN_BOOTSTRAP_USERNAME", "admin")
        email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
        password = os.getenv("ADMIN_BOOTSTRAP_PASSWORD")
        if not password:
            raise CommandError("Set ADMIN_BOOTSTRAP_PASSWORD before running this command.")
        User = get_user_model()
        user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email; user.is_staff = True; user.is_superuser = True; user.is_active = True
        user.set_password(password); user.save()
        self.stdout.write(self.style.SUCCESS(f"Admin user '{username}' is ready."))
