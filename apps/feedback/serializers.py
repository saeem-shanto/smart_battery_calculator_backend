import hashlib
import secrets

from rest_framework import serializers

from apps.calculations.models import Calculation

from .models import Feedback


class FeedbackCreateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    calculation_public_id = serializers.UUIDField(required=False, allow_null=True)
    calculation_access_token = serializers.CharField(
        required=False,
        allow_blank=False,
        write_only=True,
    )

    def validate(self, attrs):
        attrs = super().validate(attrs)
        public_id = attrs.get("calculation_public_id")
        if not public_id:
            return attrs

        try:
            calculation = Calculation.objects.select_related("owner").get(public_id=public_id)
        except Calculation.DoesNotExist as exc:
            raise serializers.ValidationError(
                {"calculation_public_id": "Calculation not found."}
            ) from exc

        request = self.context.get("request")
        user = getattr(request, "user", None)
        authenticated = bool(user and getattr(user, "is_authenticated", False))

        if calculation.owner_id is not None:
            # Once a guest calculation has been claimed, the historical guest
            # token is no longer an authorization mechanism anywhere, including
            # feedback linking. The owner (or staff) must authenticate with JWT.
            if not authenticated or not (
                getattr(user, "is_staff", False) or calculation.owner_id == user.id
            ):
                raise serializers.ValidationError(
                    {
                        "calculation_public_id": (
                            "This calculation can only be linked by its authenticated owner or an administrator."
                        )
                    }
                )
        else:
            token = attrs.get("calculation_access_token")
            if not token:
                raise serializers.ValidationError(
                    {
                        "calculation_access_token": (
                            "Required when linking feedback to a retained guest calculation."
                        )
                    }
                )
            digest = hashlib.sha256(token.encode()).hexdigest()
            if not secrets.compare_digest(digest, calculation.access_token_hash):
                raise serializers.ValidationError(
                    {"calculation_access_token": "Invalid calculation access token."}
                )

        attrs["calculation_obj"] = calculation
        return attrs

    def create(self, validated_data):
        calculation = validated_data.pop("calculation_obj", None)
        validated_data.pop("calculation_public_id", None)
        validated_data.pop("calculation_access_token", None)
        return Feedback.objects.create(calculation=calculation, **validated_data)


class FeedbackResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ["id", "rating", "comment", "created_at"]
