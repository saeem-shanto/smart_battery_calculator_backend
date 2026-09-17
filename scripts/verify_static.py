#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.staticfiles import finders  # noqa: E402

checks = {
    "Django admin CSS": "admin/css/base.css",
    "Project CSS": "battery-api.css",
}

print(f"STATIC_URL={settings.STATIC_URL}")
print(f"STATIC_ROOT={settings.STATIC_ROOT}")
print(f"STATICFILES_DIRS={settings.STATICFILES_DIRS}")

failed = False
for label, path in checks.items():
    resolved = finders.find(path)
    status = "OK" if resolved else "MISSING"
    print(f"[{status}] {label}: {path} -> {resolved}")
    failed = failed or not bool(resolved)

sidecar_candidates = [
    "drf_spectacular_sidecar/swagger-ui-dist/swagger-ui.css",
    "drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js",
]
found_sidecar = [(p, finders.find(p)) for p in sidecar_candidates]
if any(result for _, result in found_sidecar):
    for p, result in found_sidecar:
        print(f"[{'OK' if result else 'INFO'}] Swagger sidecar: {p} -> {result}")
else:
    print("[MISSING] Swagger sidecar assets were not found. Is drf-spectacular-sidecar installed?")
    failed = True

root = Path(settings.STATIC_ROOT)
if root.exists():
    print(f"[INFO] collected static directory exists: {root}")
else:
    print("[INFO] STATIC_ROOT does not exist yet. Run collectstatic for production.")

sys.exit(1 if failed else 0)
