from rest_framework import serializers

class CalculationRequestSerializer(serializers.Serializer):
    source_mode=serializers.ChoiceField(choices=["simplified","upload"])
    upload_token=serializers.UUIDField(required=False,allow_null=True)
    daily_consumption_kwh=serializers.FloatField(required=False,min_value=1,max_value=200)
    occupants=serializers.IntegerField(required=False,min_value=1,max_value=20,default=2)
    afternoon_occupancy=serializers.BooleanField(required=False,default=False)
    pv_size_kw=serializers.FloatField(min_value=0,max_value=50)
    tariff_id=serializers.UUIDField(required=False,allow_null=True)
    custom_import_rate=serializers.FloatField(required=False,min_value=0,max_value=5)
    custom_feed_in_rate=serializers.FloatField(required=False,min_value=0,max_value=5)
    custom_daily_supply_charge=serializers.FloatField(required=False,min_value=0,max_value=20,default=0)
    custom_demand_charge_rate_per_kw_day=serializers.FloatField(required=False,min_value=0,max_value=100,default=0)
    battery_annual_cost_per_kwh=serializers.FloatField(min_value=0,max_value=1000,default=50)
    battery_installed_cost_per_kwh=serializers.FloatField(min_value=0,max_value=10000,default=1000)
    max_battery_capacity_kwh=serializers.FloatField(min_value=1,max_value=200,default=50)

    def validate(self, attrs):
        mode=attrs["source_mode"]
        if mode=="simplified" and attrs.get("daily_consumption_kwh") is None:
            raise serializers.ValidationError({"daily_consumption_kwh":"Required for simplified calculations."})
        if mode=="upload" and not attrs.get("upload_token"):
            raise serializers.ValidationError({"upload_token":"Required for upload calculations."})
        if not attrs.get("tariff_id") and attrs.get("custom_import_rate") is None:
            raise serializers.ValidationError({"custom_import_rate":"Provide tariff_id or a custom import rate."})
        return attrs

class CalculationResponseSerializer(serializers.Serializer):
    public_id=serializers.UUIDField()
    access_token=serializers.CharField()
    status=serializers.CharField()
    result=serializers.DictField()
    assumptions=serializers.ListField(child=serializers.CharField())
    warnings=serializers.ListField(child=serializers.CharField())
    algorithm_version=serializers.CharField()
    runtime_ms=serializers.IntegerField()
    created_at=serializers.DateTimeField()
