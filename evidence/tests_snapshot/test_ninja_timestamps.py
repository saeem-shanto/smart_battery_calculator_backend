"""Regression tests for Renewables.ninja timestamp formats."""
from datetime import datetime, timezone
from django.test import SimpleTestCase
from apps.calculations.services.generated_profiles import _parse_utc_timestamp, ProfileGenerationError


class RenewablesNinjaTimestampTests(SimpleTestCase):
    def test_milliseconds_for_2024(self):
        self.assertEqual(_parse_utc_timestamp("1704067200000"), datetime(2024, 1, 1, tzinfo=timezone.utc))

    def test_seconds_for_2024(self):
        self.assertEqual(_parse_utc_timestamp("1704067200"), datetime(2024, 1, 1, tzinfo=timezone.utc))

    def test_iso8601_utc(self):
        self.assertEqual(_parse_utc_timestamp("2024-01-01T00:00:00Z"), datetime(2024, 1, 1, tzinfo=timezone.utc))

    def test_iso8601_naive_assumed_utc(self):
        self.assertEqual(_parse_utc_timestamp("2024-01-01 00:00:00"), datetime(2024, 1, 1, tzinfo=timezone.utc))

    def test_rejects_bad_timestamp(self):
        with self.assertRaises(ProfileGenerationError):
            _parse_utc_timestamp("unexpected")
