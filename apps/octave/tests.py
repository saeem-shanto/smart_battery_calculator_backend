from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(OCTAVE_TEST_ENABLED=False)
class DisabledOctaveApiTests(TestCase):
    def test_status_hidden_when_disabled(self):
        response = APIClient().get("/api/v1/octave/status/")
        self.assertEqual(response.status_code, 404)


@override_settings(OCTAVE_TEST_ENABLED=True)
class OctaveApiTests(TestCase):
    @patch("apps.octave.views.OctaveEngine.status")
    def test_status_reports_runtime(self, mocked_status):
        mocked_status.return_value = {
            "runtime_ready": True,
            "octave_path": "/usr/bin/octave-cli",
            "octave_version": "GNU Octave test",
        }
        response = APIClient().get("/api/v1/octave/status/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["runtime_ready"])
