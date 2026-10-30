"""Regression checks for compass bearings forwarded to Renewables.ninja."""
import os
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.calculations.services import generated_profiles


class PvAzimuthConventionTests(SimpleTestCase):
    def test_southern_hemisphere_cardinal_bearings(self):
        compass = (0, 90, 180, 270, 360)
        expected = (180.0, 270.0, 0.0, 90.0, 180.0)
        for bearing, result in zip(compass, expected):
            with self.subTest(bearing=bearing):
                self.assertEqual(generated_profiles.ninja_azimuth(bearing, -34.9), result)

    def test_northern_hemisphere_bearings_unchanged(self):
        compass = (0, 90, 180, 270, 360)
        expected = (0.0, 90.0, 180.0, 270.0, 0.0)
        for bearing, result in zip(compass, expected):
            with self.subTest(bearing=bearing):
                self.assertEqual(generated_profiles.ninja_azimuth(bearing, 51.5), result)

    def test_api_parameter_and_cache_key_use_converted_bearing(self):
        with patch.object(generated_profiles, "cache") as fake_cache, \
             patch.object(generated_profiles.requests, "get") as fake_get, \
             patch.dict(os.environ, {"RENEWABLES_NINJA_API_TOKEN": "test-only"}):
            fake_cache.get.return_value = None
            fake_get.return_value.json.return_value = {"data": {}}
            with self.assertRaises(generated_profiles.ProfileGenerationError):
                generated_profiles._annual_pv(
                    -34.9, 138.6, "Australia/Adelaide", 2023, 25, 0, 0.1
                )
            self.assertEqual(fake_get.call_args.kwargs["params"]["azim"], 180.0)
            self.assertTrue(
                fake_cache.get.call_args.args[0].startswith("ninja-pv-v4:")
            )

    def test_southern_hemisphere_south_maps_to_zero(self):
        with patch.object(generated_profiles, "cache") as fake_cache, \
             patch.object(generated_profiles.requests, "get") as fake_get, \
             patch.dict(os.environ, {"RENEWABLES_NINJA_API_TOKEN": "test-only"}):
            fake_cache.get.return_value = None
            fake_get.return_value.json.return_value = {"data": {}}
            with self.assertRaises(generated_profiles.ProfileGenerationError):
                generated_profiles._annual_pv(
                    -34.9, 138.6, "Australia/Adelaide", 2023, 25, 180, 0.1
                )
            self.assertEqual(fake_get.call_args.kwargs["params"]["azim"], 0.0)
