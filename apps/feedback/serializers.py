import hashlib
import secrets
from rest_framework import serializers
from apps.calculations.models import Calculation
from .models import Feedback

class FeedbackCreateSerializer(serializers.Serializer):
    rating=serializers.IntegerField(min_value=1,max_value=5)
    comment=serializers.CharField(required=False,allow_blank=True,max_length=2000)
    calculation_public_id=serializers.UUIDField(required=False,allow_null=True)
    calculation_access_token=serializers.CharField(required=False,allow_blank=False,write_only=True)
    def validate(self,attrs):
        pid=attrs.get("calculation_public_id")
        if pid:
            token=attrs.get("calculation_access_token")
            if not token: raise serializers.ValidationError({"calculation_access_token":"Required when linking feedback to a calculation."})
            try: obj=Calculation.objects.get(public_id=pid)
            except Calculation.DoesNotExist as exc: raise serializers.ValidationError({"calculation_public_id":"Calculation not found."}) from exc
            digest=hashlib.sha256(token.encode()).hexdigest()
            if not secrets.compare_digest(digest,obj.access_token_hash):
                raise serializers.ValidationError({"calculation_access_token":"Invalid calculation access token."})
            attrs["calculation_obj"]=obj
        return attrs
    def create(self,validated_data):
        calc=validated_data.pop("calculation_obj",None)
        validated_data.pop("calculation_public_id",None); validated_data.pop("calculation_access_token",None)
        return Feedback.objects.create(calculation=calc,**validated_data)

class FeedbackResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model=Feedback
        fields=["id","rating","comment","created_at"]
