"""Transient profile generation: no calculation or household input persistence."""
import math

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from .serializers import CalculationCreateResponseSerializer
from .services.generated_profiles import ProfileGenerationError, build_generated_csv, build_generated_profile
from .views import ClientWorkbookCalculationView


class GeneratedProfileSerializer(serializers.Serializer):
    postcode = serializers.RegexField(regex=r"^\d{4}$")
    state = serializers.ChoiceField(choices=["SA", "NSW", "VIC", "QLD", "WA", "TAS", "ACT", "NT"])
    load_profile_24h = serializers.ListField(child=serializers.FloatField(min_value=0), min_length=24, max_length=24)
    year = serializers.IntegerField(min_value=2000, max_value=2024, default=2024)
    tilt = serializers.FloatField(min_value=0, max_value=90, default=25)
    azimuth = serializers.FloatField(min_value=0, max_value=360, default=0)
    system_loss = serializers.FloatField(min_value=0, max_value=0.9, default=0.1)

    def validate_load_profile_24h(self, values):
        if any(not math.isfinite(value) for value in values):
            raise serializers.ValidationError("All hourly values must be finite numbers.")
        return values


class GeneratedCalculationSerializer(GeneratedProfileSerializer):
    suburb = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    retain_data = serializers.BooleanField(required=False, default=False)
    battery_installed_cost_per_kwh = serializers.FloatField(min_value=0, max_value=10000, default=1000)


class GenerateAnnualProfileView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "calculations"

    def post(self, request):
        serializer = GeneratedProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            result = build_generated_csv(postcode=d["postcode"], state=d["state"], load=d["load_profile_24h"], year=d["year"], tilt=d["tilt"], azimuth=d["azimuth"], loss=d["system_loss"])
        except ProfileGenerationError as exc:
            raise ValidationError({"profile": str(exc)}) from exc
        response = Response(result)
        response["Cache-Control"] = "no-store"
        return response


class GeneratedAnnualCalculationView(ClientWorkbookCalculationView):
    """One JSON request -> annual profiles -> existing workbook/MATLAB executor.

    The generated CSV is never sent to the browser or re-uploaded. Retention
    remains opt-in and is handled by the exact same execution path as uploads.
    """
    parser_classes = [JSONParser]

    @extend_schema(
        tags=["Calculations"],
        summary="Generate annual PV and load data and run the original MATLAB algorithm",
        description=("Submit a postcode, 24 hourly household load values, historical PV year, and solar settings. "
                     "The server fetches hourly PV from Renewables.ninja, generates the 8760x2 legacy input "
                     "internally and executes the original model. No file round trip to the frontend. "
                     "With retain_data=false, no calculation or input records are stored."),
        request=GeneratedCalculationSerializer,
        responses={200: CalculationCreateResponseSerializer, 201: CalculationCreateResponseSerializer},
    )
    def post(self, request):
        serializer = GeneratedCalculationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            generated = build_generated_profile(
                postcode=d["postcode"], state=d["state"],
                load=d["load_profile_24h"], year=d["year"],
                tilt=d["tilt"], azimuth=d["azimuth"], loss=d["system_loss"],
            )
        except ProfileGenerationError as exc:
            raise ValidationError({"profile": str(exc)}) from exc

        upload = SimpleUploadedFile(generated["filename"], generated["csv_bytes"], content_type="text/csv")
        metadata = {
            "frontend": "nextjs-direct-api",
            "workflow": "generated_annual_profile",
            "simulation_year": d["year"],
            "pv_tilt_degrees": d["tilt"],
            "pv_azimuth_degrees": d["azimuth"],
            "pv_system_loss_fraction": d["system_loss"],
            "solar_location_approximate": generated["location"]["approximate"],
            "annual_pv_kwh": generated["annual_pv_kwh"],
            "annual_load_kwh": generated["annual_load_kwh"],
        }
        attrs = {
            "postcode": d["postcode"],
            "state": d["state"],
            "suburb": d["suburb"],
            "retain_data": d["retain_data"],
            "battery_installed_cost_per_kwh": d["battery_installed_cost_per_kwh"],
            "metadata": metadata,
        }
        response = self._run_upload(request, attrs, upload, extra_warnings=generated["warnings"])
        response["Cache-Control"] = "no-store"
        return response
