"""Contract tests for the one-request postcode calculation route.

Run with: python manage.py test apps.calculations.tests_generated
No live Renewables.ninja API key or GNU Octave binary is required here.
"""
from unittest.mock import patch
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from apps.calculations.generated_views import GeneratedAnnualCalculationView
from apps.calculations.services.executor import EngineExecution


class OneRequestGeneratedCalculationTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.payload = {
            "postcode": "5000", "state": "SA", "year": 2024,
            "load_profile_24h": [float(i % 5) for i in range(24)],
            "tilt": 25, "azimuth": 0, "system_loss": 0.1,
            "retain_data": False,
            "battery_installed_cost_per_kwh": 1000,
        }

    @patch("apps.calculations.views.execute_calculation")
    @patch("apps.calculations.services.generated_profiles._annual_pv")
    @patch("apps.calculations.services.generated_profiles.postcode_coordinates")
    def test_generated_path_passes_exact_profiles_to_engine_without_database(self, lookup, pv, execute):
        lookup.return_value = {"latitude": -34.9, "longitude": 138.6, "place": "Adelaide", "approximate": False}
        pv.return_value = [2.0] * 8760
        def fake_execution(data):
            self.assertEqual(len(data.pv_kwh), 8760)
            self.assertEqual(len(data.load_kwh), 8760)
            self.assertEqual(data.load_kwh[:24], self.payload["load_profile_24h"])
            self.assertEqual(data.load_kwh[24:48], self.payload["load_profile_24h"])
            self.assertAlmostEqual(data.pv_kwh[1] * (1742.7 / 1737) * (5 / 3), 2.0, places=6)
            self.assertEqual(data.battery_installed_cost_per_kwh, 1000)
            return EngineExecution(engine_version="mock", result={"optimal_battery_size_kwh": 6}, runtime_ms=1,
                                   artifacts={"Results_RPAtrail400.csv": b"mock_result\n"})
        execute.side_effect = fake_execution
        request = self.factory.post("/api/v1/calculations/generated-annual/", self.payload, format="json")
        response = GeneratedAnnualCalculationView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["retained"])
        self.assertEqual(response.data["postcode"], "5000")
        self.assertEqual(response.data["metadata"]["workflow"], "generated_annual_profile")
        self.assertIsNotNone(response.data["transient_csv"])
        self.assertEqual(response.data["input_filename"], "annual_pv_load_5000_2024.csv")
        execute.assert_called_once()
        pv.assert_called_once()

    def test_invalid_daily_profile_rejected_before_external_request(self):
        self.payload["load_profile_24h"] = [1.0] * 23
        request = self.factory.post("/api/v1/calculations/generated-annual/", self.payload, format="json")
        response = GeneratedAnnualCalculationView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_unsupported_future_year_rejected(self):
        self.payload["year"] = 2026
        request = self.factory.post("/api/v1/calculations/generated-annual/", self.payload, format="json")
        response = GeneratedAnnualCalculationView.as_view()(request)
        self.assertEqual(response.status_code, 400)
