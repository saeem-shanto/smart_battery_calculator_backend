import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from .parsers import parse_profile_file


class ProfileParserTests(SimpleTestCase):
    def test_combined_timestamp_csv(self):
        content = b"timestamp,pv,load\n2026-01-01T00:00:00,0,0.4\n2026-01-01T01:00:00,0,0.5\n"
        upload = SimpleUploadedFile("profile.csv", content, content_type="text/csv")
        parsed = parse_profile_file(upload, "combined", "energy_kwh_interval")
        self.assertEqual(parsed.interval_minutes, 60)
        self.assertEqual(parsed.pv_values, [0.0, 0.0])
        self.assertEqual(parsed.load_values, [0.4, 0.5])

    def test_headerless_matlab_convention(self):
        content = b"0.1,0.5\n0.2,0.6\n"
        upload = SimpleUploadedFile("two_columns.csv", content, content_type="text/csv")
        parsed = parse_profile_file(upload, "combined", "energy_kwh_interval", 60)
        self.assertEqual(parsed.pv_values, [0.1, 0.2])
        self.assertEqual(parsed.load_values, [0.5, 0.6])
