from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from .models import ProfileUpload
from .parsers import parse_profile_file, ProfileParseError
from .serializers import ProfileUploadSerializer, ProfileUploadResponseSerializer

@extend_schema(tags=["Profile Uploads"], request=ProfileUploadSerializer, responses={201: ProfileUploadResponseSerializer})
class ProfileUploadView(APIView):
    permission_classes=[AllowAny]
    throttle_scope="uploads"
    def post(self, request):
        ProfileUpload.objects.filter(expires_at__lte=timezone.now()).delete()
        s=ProfileUploadSerializer(data=request.data); s.is_valid(raise_exception=True)
        f=s.validated_data["file"]
        max_bytes=settings.PROFILE_UPLOAD_MAX_MB*1024*1024
        if f.size>max_bytes:
            raise ValidationError({"file":[f"File exceeds the {settings.PROFILE_UPLOAD_MAX_MB} MB limit."]})
        try:
            parsed=parse_profile_file(f, s.validated_data["data_role"], s.validated_data["value_kind"], s.validated_data.get("interval_minutes"))
        except ProfileParseError as exc:
            raise ValidationError({"file":[str(exc)]}) from exc
        payload={"load_values":parsed.load_values,"pv_values":parsed.pv_values,"timestamps":parsed.timestamps}
        count=len(parsed.load_values or parsed.pv_values or [])
        obj=ProfileUpload.objects.create(
            role=s.validated_data["data_role"], original_name=f.name, detected_format=parsed.detected_format,
            interval_minutes=parsed.interval_minutes, value_kind=parsed.value_kind, parsed_payload=payload, warnings=parsed.warnings,
            row_count=count, expires_at=timezone.now()+timedelta(hours=settings.PROFILE_UPLOAD_TTL_HOURS)
        )
        return Response({"upload_token":obj.id,"original_name":obj.original_name,"detected_format":obj.detected_format,
                         "data_role":obj.role,"interval_minutes":obj.interval_minutes,"value_kind":obj.value_kind,
                         "interval_count":obj.row_count,"warnings":obj.warnings,"expires_at":obj.expires_at}, status=status.HTTP_201_CREATED)
