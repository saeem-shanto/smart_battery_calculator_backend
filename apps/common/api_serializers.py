from rest_framework import serializers


class ApiErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    fields = serializers.JSONField(required=False, allow_null=True)
    request_id = serializers.CharField(required=False, allow_null=True)
    retry_after_seconds = serializers.IntegerField(required=False)
    retry_at = serializers.DateTimeField(required=False)


class ApiErrorSerializer(serializers.Serializer):
    error = ApiErrorBodySerializer()


class ApiRootResponseSerializer(serializers.Serializer):
    name = serializers.CharField()
    status = serializers.CharField()
    api_version = serializers.CharField()
    calculation_engine = serializers.CharField()
    health = serializers.CharField()
    readiness = serializers.CharField()
    swagger = serializers.CharField()
    redoc = serializers.CharField()
    schema = serializers.CharField()
    octave_diagnostics = serializers.CharField(required=False)


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    calculation_engine = serializers.CharField()
    time = serializers.DateTimeField()


class ReadinessComponentSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    detail = serializers.CharField(required=False, allow_null=True)


class ReadinessEngineSerializer(serializers.Serializer):
    ready = serializers.BooleanField()
    engine = serializers.CharField(allow_null=True)
    octave_version = serializers.CharField(allow_null=True)
    algorithm_source_present = serializers.BooleanField(allow_null=True)
    algorithm_sha256 = serializers.CharField(allow_null=True)
    detail = serializers.CharField(allow_null=True)


class ReadinessResponseSerializer(serializers.Serializer):
    # A CharField avoids an OpenAPI enum-name collision with Calculation.status
    # while the runtime endpoint still emits only "ready" or "not_ready".
    status = serializers.CharField(help_text='Either "ready" or "not_ready".')
    service = serializers.CharField()
    calculation_engine = serializers.CharField()
    database = ReadinessComponentSerializer()
    storage = ReadinessComponentSerializer(required=False)
    engine = ReadinessEngineSerializer()
