#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    # Unit tests must not create/drop databases in a developer's configured
    # Supabase project. Use isolated test settings by default, while still
    # respecting an explicitly supplied DJANGO_SETTINGS_MODULE for deliberate
    # integration testing.
    default_settings = (
        "config.settings.test"
        if "test" in sys.argv[1:]
        else "config.settings.development"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default_settings)
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
