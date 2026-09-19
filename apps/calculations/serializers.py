import json

from rest_framework import serializers


class BatteryCalculationResultSerializer(serializers.Serializer):
    optimal_battery_size_kwh = serializers.FloatField()
    net_annual_payment_aud = serializers.FloatField()
    baseline_annual_payment_aud = serializers.FloatField()
    estimated_annual_bill_reduction_aud = serializers.FloatField()
    estimated_annual_bill_reduction_percent = serializers.FloatField()
    export_to_grid_kwh_year = serializers.FloatField()
    import_from_grid_kwh_year = serializers.FloatField()
    energy_balance_import_minus_export_kwh_year = serializers.FloatField()
    annual_load_kwh = serializers.FloatField()
    annual_pv_generation_kwh = serializers.FloatField()
    self_consumption_percent = serializers.FloatField()
    baseline_self_consumption_percent = serializers.FloatField()
    battery_annual_payment_rate_aud_per_kwh_year = serializers.FloatField()
    battery_upfront_cost_aud = serializers.FloatField()
    simple_payback_years = serializers.FloatField(allow_null=True)
    average_retail_price_aud_per_kwh = serializers.FloatField()
    average_feed_in_tariff_aud_per_kwh = serializers.FloatField()
    annual_demand_charge_aud = serializers.FloatField()
    pv_size_kw = serializers.FloatField()
    optimizer_success = serializers.BooleanField()
    optimizer_exitflag = serializers.IntegerField()
    objective_value = serializers.FloatField()
    engine = serializers.CharField()
    algorithm_source = serializers.CharField()
    algorithm_sha256 = serializers.CharField()
    profile_duration_hours = serializers.IntegerField()
    profile_is_full_year = serializers.BooleanField()


class CalculationFileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    filename = serializers.CharField()
    original_filename = serializers.CharField(allow_blank=True)
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    sha256 = serializers.CharField()
    download_path = serializers.CharField()
    delete_path = serializers.CharField(required=False)


class CalculationDetailResponseSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    status = serializers.CharField()
    postcode = serializers.CharField(allow_blank=True)
    suburb = serializers.CharField(allow_blank=True)
    state = serializers.CharField(allow_blank=True)
    metadata = serializers.JSONField()
    input_filename = serializers.CharField(allow_null=True)
    result = BatteryCalculationResultSerializer()
    assumptions = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())
    algorithm_version = serializers.CharField()
    runtime_ms = serializers.IntegerField()
    files = CalculationFileSerializer(many=True)
    created_at = serializers.DateTimeField()


class CalculationCreateResponseSerializer(CalculationDetailResponseSerializer):
    access_token = serializers.CharField(
        help_text="Returned once. Store it securely and send it later in X-Calculation-Token."
    )


class ClientWorkbookCalculationSerializer(serializers.Serializer):
    file = serializers.FileField(
        help_text=(
            "Original client workbook. XLS/XLSX/CSV/TXT are accepted; column 1 is the legacy/base PV profile and "
            "column 2 is household load. The uploaded filename and exact bytes are preserved while the stored input exists."
        )
    )
    consent = serializers.BooleanField(
        help_text="Must be true to confirm storage and processing of the uploaded household energy file."
    )
    postcode = serializers.RegexField(
        regex=r"^\d{4}$",
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional Australian 4-digit postcode stored with the calculation record for admin search/filtering.",
    )
    suburb = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
    state = serializers.CharField(required=False, allow_blank=True, default="", max_length=40)
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text=(
            "Optional JSON object for additional non-algorithm record information, e.g. property type, scenario label, "
            "or project reference. In multipart/form-data this may be sent as a JSON string."
        ),
    )
    battery_installed_cost_per_kwh = serializers.FloatField(
        min_value=0,
        max_value=10000,
        default=1000,
        help_text=(
            "Installed battery cost used only for Django's simple-payback report (AUD/kWh). "
            "It does not alter the immutable MATLAB optimisation source."
        ),
    )

    def validate_consent(self, value):
        if value is not True:
            raise serializers.ValidationError(
                "Consent to store and process the uploaded household energy file is required."
            )
        return value

    def validate_metadata(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError("Metadata must be a valid JSON object.") from exc
        if value in (None, ""):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Metadata must be a JSON object.")
        return value
