from rest_framework import serializers

from apps.calculations.serializers import BatteryCalculationResultSerializer


class OctaveTestSerializer(serializers.Serializer):
    pv_profile = serializers.ListField(
        child=serializers.FloatField(min_value=0), min_length=2, max_length=100_000,
        help_text="Legacy/base PV profile values, one value per hour.",
    )
    load_profile = serializers.ListField(
        child=serializers.FloatField(min_value=0), min_length=2, max_length=100_000,
        help_text="Household load values in kWh, one value per hour.",
    )
    battery_installed_cost_per_kwh = serializers.FloatField(min_value=0, max_value=10000, default=1000)

    def validate(self, attrs):
        if len(attrs["pv_profile"]) != len(attrs["load_profile"]):
            raise serializers.ValidationError("pv_profile and load_profile must have the same length.")
        return attrs


class OctaveFileSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Client workbook; first two columns are legacy PV base profile and load.")
    battery_installed_cost_per_kwh = serializers.FloatField(min_value=0, max_value=10000, default=1000)


class OctaveStatusSerializer(serializers.Serializer):
    engine = serializers.CharField()
    runtime_ready = serializers.BooleanField()
    octave_executable = serializers.CharField()
    octave_path = serializers.CharField(allow_null=True)
    octave_version = serializers.CharField(allow_null=True)
    algorithm_source_present = serializers.BooleanField()
    bridge_present = serializers.BooleanField()
    algorithm_files = serializers.DictField(child=serializers.CharField())
    algorithm_sha256 = serializers.CharField(allow_null=True)
    legacy_input_filename = serializers.CharField()
    legacy_output_filename = serializers.CharField()
    serialize_calls = serializers.BooleanField()
    timeout_seconds = serializers.IntegerField()
    error = serializers.CharField(allow_null=True)
    enabled = serializers.BooleanField()
    calculation_engine = serializers.CharField()


class OctaveTestResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    runtime_ms = serializers.IntegerField()
    result = BatteryCalculationResultSerializer()


class OctaveFileTestResponseSerializer(serializers.Serializer):
    ok = serializers.BooleanField()
    runtime_ms = serializers.IntegerField()
    detected_format = serializers.CharField()
    input_rows = serializers.IntegerField()
    warnings = serializers.ListField(child=serializers.CharField())
    result = BatteryCalculationResultSerializer()
