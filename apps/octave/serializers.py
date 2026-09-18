from rest_framework import serializers


class OctaveTestSerializer(serializers.Serializer):
    pv_profile = serializers.ListField(
        child=serializers.FloatField(min_value=0), min_length=2, max_length=100_000
    )
    load_profile = serializers.ListField(
        child=serializers.FloatField(min_value=0), min_length=2, max_length=100_000
    )
    profile_is_base_pv = serializers.BooleanField(default=True)
    pv_size_kw = serializers.FloatField(min_value=0, max_value=50, default=5)
    battery_annual_cost_per_kwh = serializers.FloatField(min_value=0, max_value=1000, default=50)
    battery_installed_cost_per_kwh = serializers.FloatField(min_value=0, max_value=10000, default=1000)
    retail_price_per_kwh = serializers.FloatField(min_value=0, max_value=5, default=0.3773)
    feed_in_tariff_per_kwh = serializers.FloatField(min_value=0, max_value=5, default=0.124)
    max_battery_capacity_kwh = serializers.FloatField(min_value=0.1, max_value=200, default=50)

    def validate(self, attrs):
        if len(attrs["pv_profile"]) != len(attrs["load_profile"]):
            raise serializers.ValidationError("pv_profile and load_profile must have the same length.")
        return attrs


class OctaveFileSerializer(serializers.Serializer):
    file = serializers.FileField()
    pv_size_kw = serializers.FloatField(min_value=0, max_value=50, default=5)
    battery_annual_cost_per_kwh = serializers.FloatField(min_value=0, max_value=1000, default=50)
    battery_installed_cost_per_kwh = serializers.FloatField(min_value=0, max_value=10000, default=1000)
    retail_price_per_kwh = serializers.FloatField(min_value=0, max_value=5, default=0.3773)
    feed_in_tariff_per_kwh = serializers.FloatField(min_value=0, max_value=5, default=0.124)
    max_battery_capacity_kwh = serializers.FloatField(min_value=0.1, max_value=200, default=50)
