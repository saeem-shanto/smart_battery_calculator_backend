import json
from pathlib import Path

from django.conf import settings
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


class TransientCsvSerializer(serializers.Serializer):
    filename = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    sha256 = serializers.CharField()
    base64_data = serializers.CharField(
        help_text="Base64-encoded Results_RPAtrail400.csv returned only when retain_data=false. The backend does not persist it."
    )


class CalculationDetailResponseSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    retained = serializers.BooleanField(default=True)
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
    transient_csv = TransientCsvSerializer(required=False, allow_null=True)
    created_at = serializers.DateTimeField()


class CalculationCreateResponseSerializer(serializers.Serializer):
    public_id = serializers.UUIDField(allow_null=True)
    access_token = serializers.CharField(
        required=False,
        allow_null=True,
        help_text=("Returned for retained guest calculations. Authenticated owners use their Bearer JWT instead; "
            "transient calculations return null."),
    )
    retained = serializers.BooleanField()
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
    transient_csv = TransientCsvSerializer(required=False, allow_null=True)
    created_at = serializers.DateTimeField()


class ClientWorkbookCalculationSerializer(serializers.Serializer):
    file = serializers.FileField(
        help_text=(
            "Original client workbook. XLS/XLSX/CSV/TXT are accepted; column 1 is the legacy/base PV profile and "
            "column 2 is household load."
        )
    )
    retain_data = serializers.BooleanField(
        required=False,
        default=False,
        help_text=(
            "Privacy/retention choice. If true, the unique input, canonical Results_RPAtrail400.csv and calculation "
            "record are persisted for later download/admin audit. If false, the request is processed transiently, "
            "no application database rows or file bytes are retained, and the CSV is returned inline in the response."
        ),
    )
    consent = serializers.BooleanField(
        required=False,
        help_text=(
            "Deprecated compatibility field. Older clients that omit retain_data use this value as the retention choice. "
            "New clients should send retain_data explicitly."
        ),
    )
    postcode = serializers.RegexField(
        regex=r"^\d{4}$",
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional Australian 4-digit postcode. Persisted only when retain_data=true.",
    )
    suburb = serializers.CharField(required=False, allow_blank=True, default="", max_length=120)
    state = serializers.CharField(required=False, allow_blank=True, default="", max_length=40)
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text=(
            "Optional JSON object for non-algorithm record information. Persisted only when retain_data=true. "
            "In multipart/form-data this may be sent as a JSON string."
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

    def validate_file(self, value):
        max_bytes = settings.PROFILE_UPLOAD_MAX_MB * 1024 * 1024
        if getattr(value, "size", 0) > max_bytes:
            raise serializers.ValidationError(
                f"File exceeds the {settings.PROFILE_UPLOAD_MAX_MB} MB upload limit."
            )
        suffix = Path(value.name or "").suffix.lower()
        if suffix not in {".xls", ".xlsx", ".csv", ".txt"}:
            raise serializers.ValidationError("Supported file formats are XLS, XLSX, CSV and TXT.")
        if getattr(value, "size", 0) == 0:
            raise serializers.ValidationError("The uploaded file is empty.")
        return value

    def validate(self, attrs):
        # Backward compatibility for the v1.3 Postman/frontend contract. New
        # clients should always send retain_data explicitly. Privacy-safe
        # default remains false when neither field is supplied.
        if "retain_data" not in self.initial_data:
            attrs["retain_data"] = bool(attrs.get("consent", False))
        return attrs

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
