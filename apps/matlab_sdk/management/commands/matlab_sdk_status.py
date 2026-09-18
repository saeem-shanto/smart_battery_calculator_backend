import json

from django.core.management.base import BaseCommand

from apps.calculations.services.matlab_compiled import MatlabCompiledEngine


class Command(BaseCommand):
    help = "Check whether the compiled MATLAB package and MATLAB Runtime can initialize."

    def handle(self, *args, **options):
        status = MatlabCompiledEngine().status()
        self.stdout.write(json.dumps(status, indent=2))
        if not status.get("runtime_ready"):
            raise SystemExit(2)
