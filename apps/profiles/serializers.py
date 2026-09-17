from rest_framework import serializers

class ProfileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    data_role = serializers.ChoiceField(choices=["load","pv","combined"])
    value_kind = serializers.ChoiceField(choices=["auto","energy_kwh_interval","power_kw"], default="auto")
    interval_minutes = serializers.IntegerField(required=False, min_value=1, max_value=1440)
    consent = serializers.BooleanField()
    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError("Consent to temporary processing is required for uploaded household data.")
        return value

class ProfileUploadResponseSerializer(serializers.Serializer):
    upload_token = serializers.UUIDField()
    original_name = serializers.CharField()
    detected_format = serializers.CharField()
    data_role = serializers.CharField()
    interval_minutes = serializers.IntegerField()
    value_kind = serializers.CharField()
    interval_count = serializers.IntegerField()
    warnings = serializers.ListField(child=serializers.CharField())
    expires_at = serializers.DateTimeField()
