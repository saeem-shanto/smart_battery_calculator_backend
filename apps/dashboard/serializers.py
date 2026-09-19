from rest_framework import serializers

from apps.calculations.artifact_access import calculation_artifacts
from apps.calculations.models import Calculation
from apps.feedback.models import Feedback
from apps.tariffs.models import TariffPlan


class AdminTariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = TariffPlan
        fields = "__all__"


class AdminFeedbackSerializer(serializers.ModelSerializer):
    calculation_public_id = serializers.UUIDField(
        source="calculation.public_id", read_only=True, allow_null=True
    )

    class Meta:
        model = Feedback
        fields = ["id", "calculation_public_id", "rating", "comment", "created_at"]


class AdminCalculationListSerializer(serializers.ModelSerializer):
    input_filename = serializers.SerializerMethodField()
    input_sha256 = serializers.SerializerMethodField()
    has_input_file = serializers.SerializerMethodField()
    has_csv_file = serializers.SerializerMethodField()
    optimal_battery_size_kwh = serializers.SerializerMethodField()
    net_annual_payment_aud = serializers.SerializerMethodField()
    estimated_annual_bill_reduction_aud = serializers.SerializerMethodField()

    class Meta:
        model = Calculation
        fields = [
            "public_id",
            "postcode",
            "suburb",
            "state",
            "status",
            "input_filename",
            "input_sha256",
            "has_input_file",
            "has_csv_file",
            "optimal_battery_size_kwh",
            "net_annual_payment_aud",
            "estimated_annual_bill_reduction_aud",
            "algorithm_version",
            "runtime_ms",
            "created_at",
            "updated_at",
        ]

    def get_input_filename(self, obj):
        return (obj.input_payload or {}).get("original_filename")

    def get_input_sha256(self, obj):
        return (obj.input_payload or {}).get("input_sha256")

    def get_has_input_file(self, obj):
        return bool(obj.input_file_id)

    def get_has_csv_file(self, obj):
        return bool(obj.csv_result_id)

    def get_optimal_battery_size_kwh(self, obj):
        return (obj.result_payload or {}).get("optimal_battery_size_kwh")

    def get_net_annual_payment_aud(self, obj):
        return (obj.result_payload or {}).get("net_annual_payment_aud")

    def get_estimated_annual_bill_reduction_aud(self, obj):
        return (obj.result_payload or {}).get("estimated_annual_bill_reduction_aud")


class AdminCalculationSerializer(serializers.ModelSerializer):
    files = serializers.SerializerMethodField()
    input_filename = serializers.SerializerMethodField()
    input_sha256 = serializers.SerializerMethodField()

    class Meta:
        model = Calculation
        fields = [
            "public_id",
            "postcode",
            "suburb",
            "state",
            "metadata",
            "status",
            "source_mode",
            "input_filename",
            "input_sha256",
            "input_payload",
            "result_payload",
            "assumptions",
            "warnings",
            "algorithm_version",
            "runtime_ms",
            "error_code",
            "error_message",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "public_id",
            "status",
            "source_mode",
            "input_filename",
            "input_sha256",
            "input_payload",
            "result_payload",
            "assumptions",
            "warnings",
            "algorithm_version",
            "runtime_ms",
            "error_code",
            "error_message",
            "files",
            "created_at",
            "updated_at",
        ]

    def get_files(self, obj):
        return calculation_artifacts(obj, admin=True)

    def get_input_filename(self, obj):
        return (obj.input_payload or {}).get("original_filename")

    def get_input_sha256(self, obj):
        return (obj.input_payload or {}).get("input_sha256")


class CountSummarySerializer(serializers.Serializer):
    today = serializers.IntegerField()
    last_7_days = serializers.IntegerField()
    last_30_days = serializers.IntegerField()
    all_time = serializers.IntegerField()


class SourceModeSummarySerializer(serializers.Serializer):
    source_mode = serializers.CharField()
    count = serializers.IntegerField()


class FeedbackSummarySerializer(serializers.Serializer):
    last_30_days = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)


class AdminSummarySerializer(serializers.Serializer):
    calculations = CountSummarySerializer()
    source_modes = SourceModeSummarySerializer(many=True)
    average_runtime_ms = serializers.FloatField()
    feedback = FeedbackSummarySerializer()
    recent = AdminCalculationListSerializer(many=True)
