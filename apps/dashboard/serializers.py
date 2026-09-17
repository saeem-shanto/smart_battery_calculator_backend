from rest_framework import serializers

from apps.tariffs.models import TariffPlan
from apps.feedback.models import Feedback


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
        fields = [
            "id",
            "calculation_public_id",
            "rating",
            "comment",
            "created_at",
        ]
