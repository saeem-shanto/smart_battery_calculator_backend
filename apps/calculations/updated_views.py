"""Transient, single-request endpoint for the updated batt_cal_v1 MATLAB script."""
from __future__ import annotations

import base64
import csv
import hashlib
import io

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.api_exceptions import BadGateway, ServiceUnavailable
from .generated_views import GeneratedProfileSerializer
from .services.errors import CalculationEngineExecutionError, CalculationEngineUnavailable
from .services.generated_profiles import ProfileGenerationError, build_generated_profile
from .services.updated_battery_engine import (
    RETAIL_DEFAULT, FEED_DEFAULT, UpdatedBatteryEngine, UpdatedModelSettings,
    validate_settings,
)


class UpdatedCalculationSerializer(GeneratedProfileSerializer):
    suburb = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    retain_data = serializers.BooleanField(default=False, required=False)
    battery_capacity_kwh = serializers.FloatField(min_value=1, max_value=50, default=15)
    pv_capacity_kw = serializers.FloatField(min_value=0.5, max_value=30, default=6)
    interest_rate_percent = serializers.FloatField(min_value=0, max_value=20, default=2)
    installation_cost_aud = serializers.FloatField(min_value=0, max_value=100000, default=8000)
    loan_period_years = serializers.IntegerField(min_value=1, max_value=30, default=10)
    daily_supply_charge_aud = serializers.FloatField(min_value=0, max_value=5, default=1.01)
    retail_tariff_24h = serializers.ListField(child=serializers.FloatField(min_value=0, max_value=5), min_length=24, max_length=24, default=list(RETAIL_DEFAULT))
    feed_in_tariff_24h = serializers.ListField(child=serializers.FloatField(min_value=0, max_value=5), min_length=24, max_length=24, default=list(FEED_DEFAULT))

    def validate(self, attrs):
        from math import isfinite
        for key in ("battery_capacity_kwh", "pv_capacity_kw", "interest_rate_percent", "installation_cost_aud", "daily_supply_charge_aud"):
            if not isfinite(attrs[key]):
                raise serializers.ValidationError({key: "A finite number is required."})
        for key in ("retail_tariff_24h", "feed_in_tariff_24h"):
            if not all(isfinite(value) for value in attrs[key]):
                raise serializers.ValidationError({key: "All tariff rates must be finite."})
        if sum(attrs["load_profile_24h"]) <= 0:
            raise serializers.ValidationError({"load_profile_24h": "Enter some electricity consumption; all 24 hours cannot be zero."})
        if attrs["retain_data"]:
            raise serializers.ValidationError({"retain_data": "Saving calculations for this updated model is not implemented yet. Turn off 'Save calculation data' to run privately."})
        return attrs


class UpdatedGeneratedCalculationView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]
    throttle_scope = "calculations"

    @extend_schema(
        tags=["Calculations"],
        summary="Calculate using the client's updated batt_cal_v1.m in Django/GNU Octave",
        request=UpdatedCalculationSerializer,
        description="Accepts the frontend's input fields; creates the 8760×2 profile only in Django; runs a parameterised temporary copy of the client MATLAB script; returns results without storing household data. Supports retain_data=false only.",
    )
    def post(self, request):
        serializer = UpdatedCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = UpdatedModelSettings(
            battery_capacity_kwh=data["battery_capacity_kwh"],
            pv_capacity_kw=data["pv_capacity_kw"],
            interest_rate_percent=data["interest_rate_percent"],
            installation_cost_aud=data["installation_cost_aud"],
            loan_period_years=data["loan_period_years"],
            daily_supply_charge_aud=data["daily_supply_charge_aud"],
            retail_tariff_24h=tuple(data["retail_tariff_24h"]),
            feed_in_tariff_24h=tuple(data["feed_in_tariff_24h"]),
        )
        try:
            validate_settings(params)
            profile = build_generated_profile(
                postcode=data["postcode"], state=data["state"], load=data["load_profile_24h"],
                year=data["year"], tilt=data["tilt"], azimuth=data["azimuth"], loss=data["system_loss"],
            )
            # Generated CSV stays on the server; no 8760-row round trip to the browser.
            reader = csv.reader(io.StringIO(profile["csv_bytes"].decode("utf-8-sig")))
            next(reader)
            columns = [(float(pv), float(load)) for pv, load in reader]
            if len(columns) != 8760:
                raise ValueError("Annual profile must have exactly 8,760 rows.")
            result, csv_bytes, runtime_ms = UpdatedBatteryEngine().calculate(
                [p for p, _ in columns], [load for _, load in columns], params,
            )
        except (ProfileGenerationError, ValueError) as exc:
            raise ValidationError({"calculation": str(exc)}) from exc
        except CalculationEngineUnavailable as exc:
            raise ServiceUnavailable("GNU Octave or the updated MATLAB source is unavailable.", code="updated_model_unavailable") from exc
        except CalculationEngineExecutionError as exc:
            raise BadGateway("The updated MATLAB calculation did not complete successfully.", code="updated_model_failed") from exc
        warnings = [*profile["warnings"],
                    "This model evaluates the selected battery capacity; it does not optimise battery size.",
                    "The supplied client script omits the first-hour import/export tariff charge, and its first-hour import may become negative with positive solar surplus. These original-script assumptions require client review before production use.",
                    "Simple payback is an estimate using annual operating savings before financing, while annual bill reduction includes the model's annual financing instalment."]
        response = Response({
            "public_id": None, "access_token": None, "retained": False, "status": "completed",
            "postcode": data["postcode"], "state": data["state"], "suburb": data["suburb"],
            "metadata": {"workflow": "generated_annual_profile", "model": "batt_cal_v1", "simulation_year": data["year"],
                         "solar_location_approximate": profile["location"]["approximate"]},
            "input_filename": profile["filename"], "result": result,
            "assumptions": ["Updated client batt_cal_v1 equations run in GNU Octave using an isolated parameterised copy.",
                            "PV source is Renewables.ninja with one capacity-scaled hourly series.",
                            "Daily load is repeated 365 times; daily average is calculated by Django, not the browser."],
            "warnings": warnings,
            "algorithm_version": UpdatedBatteryEngine.version, "runtime_ms": runtime_ms, "files": [],
            "transient_csv": {"filename": "Results_RPAtrail400.csv", "content_type": "text/csv",
                              "size_bytes": len(csv_bytes), "sha256": hashlib.sha256(csv_bytes).hexdigest(),
                              "base64_data": base64.b64encode(csv_bytes).decode("ascii")},
            "created_at": timezone.now(),
        }, status=status.HTTP_200_OK)
        response["Cache-Control"] = "no-store"
        return response

class UpdatedWorkbookCalculationView(APIView):
    """Optional original 2-column workbook input to updated MATLAB, still transient."""
    permission_classes = [AllowAny]
    throttle_scope = "calculations"

    from rest_framework.parsers import FormParser, MultiPartParser
    parser_classes = [FormParser, MultiPartParser]

    def post(self, request):
        import json
        from apps.profiles.client_workbook import ClientWorkbookError, parse_client_workbook
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "Please select an annual PV/load workbook."})
        try:
            raw_settings = json.loads(request.data.get("settings", "{}"))
        except (ValueError, TypeError) as exc:
            raise ValidationError({"settings": "Expected a JSON object with the MATLAB settings."}) from exc
        if not isinstance(raw_settings, dict):
            raise ValidationError({"settings": "Expected a JSON object."})
        # Reuse validation/ranges from the generated endpoint without requiring a
        # postcode or the extra 24-hour load input.
        setting_keys = (
            "battery_capacity_kwh", "pv_capacity_kw", "interest_rate_percent",
            "installation_cost_aud", "loan_period_years", "daily_supply_charge_aud",
            "retail_tariff_24h", "feed_in_tariff_24h",
        )
        class SettingsOnlySerializer(serializers.Serializer):
            battery_capacity_kwh = serializers.FloatField(min_value=1, max_value=50, default=15)
            pv_capacity_kw = serializers.FloatField(min_value=0.5, max_value=30, default=6)
            interest_rate_percent = serializers.FloatField(min_value=0, max_value=20, default=2)
            installation_cost_aud = serializers.FloatField(min_value=0, max_value=100000, default=8000)
            loan_period_years = serializers.IntegerField(min_value=1, max_value=30, default=10)
            daily_supply_charge_aud = serializers.FloatField(min_value=0, max_value=5, default=1.01)
            retail_tariff_24h = serializers.ListField(child=serializers.FloatField(min_value=0, max_value=5), min_length=24, max_length=24, default=list(RETAIL_DEFAULT))
            feed_in_tariff_24h = serializers.ListField(child=serializers.FloatField(min_value=0, max_value=5), min_length=24, max_length=24, default=list(FEED_DEFAULT))
        unknown_keys = set(raw_settings) - set(setting_keys)
        if unknown_keys:
            raise ValidationError({"settings": "Unsupported setting names: " + ", ".join(sorted(unknown_keys))})
        parsed = SettingsOnlySerializer(data=raw_settings)
        parsed.is_valid(raise_exception=True)
        d = parsed.validated_data
        params = UpdatedModelSettings(d["battery_capacity_kwh"], d["pv_capacity_kw"],
                                      d["interest_rate_percent"], d["installation_cost_aud"],
                                      d["loan_period_years"], d["daily_supply_charge_aud"],
                                      tuple(d["retail_tariff_24h"]), tuple(d["feed_in_tariff_24h"]))
        if request.data.get("retain_data", "false").lower() in ("true", "1"):
            raise ValidationError({"retain_data": "The updated model currently supports private (no-retention) calculations only."})
        try:
            workbook = parse_client_workbook(upload)
            if workbook.row_count != 8760:
                raise ValidationError({"file": "The updated algorithm requires exactly 8,760 hourly rows (remove leap day if needed)."})
            result, csv_bytes, runtime_ms = UpdatedBatteryEngine().calculate(
                workbook.pv_base_profile, workbook.load_profile, params,
            )
        except ClientWorkbookError as exc:
            raise ValidationError({"file": str(exc)}) from exc
        except ValueError as exc:
            raise ValidationError({"calculation": str(exc)}) from exc
        except CalculationEngineUnavailable as exc:
            raise ServiceUnavailable("GNU Octave or the updated MATLAB source is unavailable.", code="updated_model_unavailable") from exc
        except CalculationEngineExecutionError as exc:
            raise BadGateway("The updated MATLAB calculation did not complete successfully.", code="updated_model_failed") from exc
        response = Response({
            "public_id": None, "access_token": None, "retained": False, "status": "completed",
            "postcode": request.data.get("postcode", ""), "suburb": request.data.get("suburb", ""), "state": request.data.get("state", ""),
            "metadata": {"workflow": "uploaded_workbook", "model": "batt_cal_v1"},
            "input_filename": upload.name, "result": result,
            "assumptions": ["The uploaded file's first column is the MATLAB base PV generation profile; the second is hourly load.",
                            "The updated client model is executed in Django using GNU Octave."],
            "warnings": [*workbook.warnings,
                         "Selected-capacity scenario, not an optimisation.",
                         "Client source's first-hour import and tariff edge cases are preserved; results need client verification."],
            "algorithm_version": UpdatedBatteryEngine.version, "runtime_ms": runtime_ms, "files": [],
            "transient_csv": {"filename": "Results_RPAtrail400.csv", "content_type": "text/csv", "size_bytes": len(csv_bytes),
                              "sha256": hashlib.sha256(csv_bytes).hexdigest(), "base64_data": base64.b64encode(csv_bytes).decode("ascii")},
            "created_at": timezone.now(),
        })
        response["Cache-Control"] = "no-store"
        return response
