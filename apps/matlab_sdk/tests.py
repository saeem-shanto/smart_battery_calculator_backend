from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient


@override_settings(MATLAB_SDK_TEST_ENABLED=False)
class DisabledMatlabSdkApiTests(TestCase):
    def test_status_hidden_when_disabled(self):
        response = APIClient().get("/api/v1/matlab-sdk/status/")
        self.assertEqual(response.status_code, 404)


@override_settings(MATLAB_SDK_TEST_ENABLED=True)
class MatlabSdkApiTests(TestCase):
    @patch("apps.matlab_sdk.views.MatlabCompiledEngine.status")
    def test_status_reports_runtime(self, mocked_status):
        mocked_status.return_value = {
            "runtime_ready": True,
            "package_importable": True,
            "matlab_module_importable": True,
        }
        response = APIClient().get("/api/v1/matlab-sdk/status/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["runtime_ready"])
