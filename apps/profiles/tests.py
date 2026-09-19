import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase

from .parsers import parse_profile_file


class ProfileParserTests(SimpleTestCase):
    def test_combined_timestamp_csv(self):
        content = b"timestamp,pv,load\n2026-01-01T00:00:00,0,0.4\n2026-01-01T01:00:00,0,0.5\n"
        upload = SimpleUploadedFile("profile.csv", content, content_type="text/csv")
        parsed = parse_profile_file(upload, "combined", "energy_kwh_interval")
        self.assertEqual(parsed.interval_minutes, 60)
        self.assertEqual(parsed.pv_values, [0.0, 0.0])
        self.assertEqual(parsed.load_values, [0.4, 0.5])

    def test_headerless_client_convention(self):
        content = b"0.1,0.5\n0.2,0.6\n"
        upload = SimpleUploadedFile("two_columns.csv", content, content_type="text/csv")
        parsed = parse_profile_file(upload, "combined", "energy_kwh_interval", 60)
        self.assertEqual(parsed.pv_values, [0.1, 0.2])
        self.assertEqual(parsed.load_values, [0.5, 0.6])


class ClientWorkbookParserTests(SimpleTestCase):
    def test_client_two_column_csv(self):
        from .client_workbook import parse_client_workbook

        upload = SimpleUploadedFile(
            "client.csv",
            b"0.1,0.5\n0.2,0.6\n",
            content_type="text/csv",
        )
        parsed = parse_client_workbook(upload)
        self.assertEqual(parsed.detected_format, "client_two_column_csv")
        self.assertEqual(parsed.pv_base_profile, [0.1, 0.2])
        self.assertEqual(parsed.load_profile, [0.5, 0.6])
        self.assertEqual(parsed.row_count, 2)

    def test_client_header_row_is_allowed(self):
        from .client_workbook import parse_client_workbook

        upload = SimpleUploadedFile(
            "client.csv",
            b"pv,load\n0.1,0.5\n0.2,0.6\n",
            content_type="text/csv",
        )
        parsed = parse_client_workbook(upload)
        self.assertEqual(parsed.row_count, 2)
        self.assertTrue(any("header" in warning.lower() for warning in parsed.warnings))

class ClientWorkbookValidationEndpointTests(TestCase):
    def test_validation_endpoint_does_not_stage_or_store_profile(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from rest_framework.test import APIClient
        from .models import ProfileUpload

        client = APIClient()
        upload = SimpleUploadedFile("client.csv", b"0.1,0.5\n0.2,0.6\n", content_type="text/csv")
        with override_settings(REQUIRE_FULL_YEAR_PROFILE=False):
            response = client.post(
                "/api/v1/profiles/client-workbook/validate/",
                {"file": upload},
                format="multipart",
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["row_count"], 2)
        self.assertEqual(ProfileUpload.objects.count(), 0)
