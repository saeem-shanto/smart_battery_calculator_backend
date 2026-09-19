from django.test import SimpleTestCase, TestCase

from .services.errors import CalculationEngineExecutionError
from .services.interfaces import EngineInput
from .services.result_cache import apply_reporting_cost, canonicalize_algorithm_result
from .services.result_contract import validate_result_contract


def _engine_input():
    return EngineInput(
        load_kwh=[0.6] * 24,
        pv_kwh=[0.0] * 7 + [1.1] * 10 + [0.0] * 7,
        battery_installed_cost_per_kwh=1000,
    )


class ResultContractTests(SimpleTestCase):
    def _result(self):
        return {
            "optimal_battery_size_kwh": 5.0,
            "net_annual_payment_aud": 4.0,
            "baseline_annual_payment_aud": 5.0,
            "estimated_annual_bill_reduction_aud": 1.0,
            "estimated_annual_bill_reduction_percent": 20.0,
            "export_to_grid_kwh_year": 3.0,
            "import_from_grid_kwh_year": 5.0,
            "energy_balance_import_minus_export_kwh_year": 2.0,
            "annual_load_kwh": 14.4,
            "annual_pv_generation_kwh": 18.39349,
            "self_consumption_percent": 72.73,
            "baseline_self_consumption_percent": 50.0,
            "battery_annual_payment_rate_aud_per_kwh_year": 50.0,
            "battery_upfront_cost_aud": 5000.0,
            "simple_payback_years": 5000.0,
            "average_retail_price_aud_per_kwh": 0.3773,
            "average_feed_in_tariff_aud_per_kwh": 0.124,
            "annual_demand_charge_aud": 0.0,
            "pv_size_kw": 5.0,
            "objective_value": 4.0,
            "profile_duration_hours": 24,
            "profile_is_full_year": False,
            "optimizer_success": True,
            "optimizer_exitflag": 1,
            "algorithm_sha256": "a" * 64,
        }

    def test_valid_octave_result_is_accepted(self):
        validate_result_contract(self._result(), _engine_input())

    def test_inconsistent_savings_are_rejected(self):
        result = self._result()
        result["estimated_annual_bill_reduction_aud"] = 0.1
        with self.assertRaises(CalculationEngineExecutionError):
            validate_result_contract(result, _engine_input())

    def test_cached_algorithm_result_can_be_repriced_without_rerunning_octave(self):
        original = self._result()
        canonical = canonicalize_algorithm_result(original)
        self.assertEqual(canonical["battery_upfront_cost_aud"], 0.0)
        self.assertIsNone(canonical["simple_payback_years"])

        repriced = apply_reporting_cost(canonical, 800)
        self.assertEqual(repriced["battery_upfront_cost_aud"], 4000.0)
        self.assertEqual(repriced["simple_payback_years"], 4000.0)


class SourceIntegrityTests(SimpleTestCase):
    EXPECTED = {
        "battrail.m": (2289, "536383fe9ffe6a248f0970789ada00b791b2554445ccc64cdf14a73617f808bf"),
        "natpaymenttrail.m": (3255, "6898b5d4fad5f4ed27fbb0de6e409a3d0db5c655b60aae75678b755a5bb5a631"),
        "rpresults.m": (620, "a50f78d4570b0f82d13fe0c3be6fd5d4408747104412a86228b74bbdd4fc48e6"),
    }

    def test_client_matlab_source_snapshots_are_unchanged(self):
        import hashlib
        from pathlib import Path
        from django.conf import settings

        source_dir = Path(settings.BASE_DIR) / "matlab_source"
        for filename, (expected_size, expected_sha256) in self.EXPECTED.items():
            raw = (source_dir / filename).read_bytes()
            self.assertEqual(len(raw), expected_size, filename)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected_sha256, filename)

    def test_legacy_csv_contract_is_ten_columns(self):
        from .services.octave_engine import OctaveEngine

        raw = b"7.388,304.15,4543.76,1320.37,-3223.39,0.3773,50,0.124,50,5\n"
        values = OctaveEngine._parse_legacy_csv(raw)
        self.assertEqual(len(values), 10)
        self.assertEqual(values[0], 7.388)
        self.assertEqual(values[9], 5.0)


class IndependentArtifactDeletionTests(TestCase):
    def setUp(self):
        from .models import Calculation, StoredCsvResult, StoredInputFile

        self.input_file = StoredInputFile.objects.create(
            sha256="1" * 64,
            canonical_filename="Vanikavipuldata.xls",
            content_type="application/vnd.ms-excel",
            size_bytes=4,
            data=b"test",
            detected_format="client_two_column_xls",
            row_count=8760,
        )
        self.csv = StoredCsvResult.objects.create(
            input_file=self.input_file,
            source_input_sha256=self.input_file.sha256,
            filename="Results_RPAtrail400.csv",
            content_type="text/csv",
            size_bytes=4,
            sha256="2" * 64,
            data=b"1,2\n",
            result_payload={"optimal_battery_size_kwh": 7.388},
            engine_version="gnu-octave-original-matlab-v1",
        )
        self.calculation = Calculation.objects.create(
            access_token_hash="3" * 64,
            input_file=self.input_file,
            csv_result=self.csv,
            postcode="5000",
            suburb="Adelaide",
            state="SA",
            metadata={"scenario_label": "test"},
            status=Calculation.Status.COMPLETED,
            input_payload={
                "original_filename": "Vanikavipuldata.xls",
                "input_sha256": self.input_file.sha256,
            },
            result_payload={"optimal_battery_size_kwh": 7.388},
        )

    def test_deleting_input_keeps_csv_and_calculation_record(self):
        from .models import Calculation, StoredCsvResult

        self.input_file.delete()
        self.calculation.refresh_from_db()
        self.csv.refresh_from_db()

        self.assertIsNone(self.calculation.input_file_id)
        self.assertEqual(self.calculation.csv_result_id, self.csv.id)
        self.assertIsNone(self.csv.input_file_id)
        self.assertTrue(Calculation.objects.filter(pk=self.calculation.pk).exists())
        self.assertTrue(StoredCsvResult.objects.filter(pk=self.csv.pk).exists())

    def test_deleting_csv_keeps_input_and_calculation_record(self):
        from .models import Calculation, StoredInputFile

        self.csv.delete()
        self.calculation.refresh_from_db()

        self.assertEqual(self.calculation.input_file_id, self.input_file.id)
        self.assertIsNone(self.calculation.csv_result_id)
        self.assertTrue(Calculation.objects.filter(pk=self.calculation.pk).exists())
        self.assertTrue(StoredInputFile.objects.filter(pk=self.input_file.pk).exists())

class TransientPrivacyCalculationTests(TestCase):
    def test_no_retention_creates_no_database_rows_and_returns_inline_csv(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from rest_framework.test import APIClient

        from .models import Calculation, StoredCsvResult, StoredInputFile
        from .services.executor import EngineExecution

        result = ResultContractTests()._result()
        result.update({
            "engine": "gnu-octave-original-matlab-v1",
            "algorithm_source": "unchanged_client_matlab_files_v1",
            "profile_duration_hours": 2,
            "profile_is_full_year": False,
        })
        execution = EngineExecution(
            engine_version="gnu-octave-original-matlab-v1",
            result=result,
            runtime_ms=12,
            artifacts={"Results_RPAtrail400.csv": b"5,4,3,5,2,0.3773,50,0.124,50,5\n"},
        )
        client = APIClient()
        upload = SimpleUploadedFile("private.csv", b"0.1,0.5\n0.2,0.6\n", content_type="text/csv")

        with override_settings(REQUIRE_FULL_YEAR_PROFILE=False), patch(
            "apps.calculations.views.execute_calculation", return_value=execution
        ):
            response = client.post(
                "/api/v1/calculations/client-workbook/",
                {
                    "file": upload,
                    "retain_data": "false",
                    "postcode": "5000",
                    "battery_installed_cost_per_kwh": "1000",
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["retained"])
        self.assertIsNone(response.data["public_id"])
        self.assertEqual(response.data["files"], [])
        self.assertEqual(response.data["transient_csv"]["filename"], "Results_RPAtrail400.csv")
        self.assertEqual(Calculation.objects.count(), 0)
        self.assertEqual(StoredInputFile.objects.count(), 0)
        self.assertEqual(StoredCsvResult.objects.count(), 0)


class RetentionCompatibilitySerializerTests(SimpleTestCase):
    def test_legacy_consent_true_maps_to_retention_true(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .serializers import ClientWorkbookCalculationSerializer

        serializer = ClientWorkbookCalculationSerializer(data={
            "file": SimpleUploadedFile("x.csv", b"0,1\n", content_type="text/csv"),
            "consent": True,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertTrue(serializer.validated_data["retain_data"])

    def test_default_is_privacy_safe(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .serializers import ClientWorkbookCalculationSerializer

        serializer = ClientWorkbookCalculationSerializer(data={
            "file": SimpleUploadedFile("x.csv", b"0,1\n", content_type="text/csv"),
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["retain_data"])
