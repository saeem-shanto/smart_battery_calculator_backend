import json

from django.core.management.base import BaseCommand, CommandError

from apps.calculations.services.octave_engine import OctaveEngine


class Command(BaseCommand):
    help = "Check GNU Octave availability and the deployed battery algorithm source."

    def handle(self, *args, **options):
        status = OctaveEngine().status()
        self.stdout.write(json.dumps(status, indent=2, default=str))
        if not status.get("runtime_ready"):
            raise CommandError("GNU Octave runtime is not ready.")
        self.stdout.write(self.style.SUCCESS("GNU Octave runtime is ready."))
