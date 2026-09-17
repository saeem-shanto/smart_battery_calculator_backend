import hashlib
import secrets
import time
from uuid import UUID
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema
from .models import Calculation
from .serializers import CalculationRequestSerializer, CalculationResponseSerializer
from .services.factory import get_engine
from .services.orchestration import build_engine_input

def _hash(token): return hashlib.sha256(token.encode()).hexdigest()

def _response(obj, token):
    return {"public_id":obj.public_id,"access_token":token,"status":obj.status,"result":obj.result_payload,
            "assumptions":obj.assumptions,"warnings":obj.warnings,"algorithm_version":obj.algorithm_version,
            "runtime_ms":obj.runtime_ms,"created_at":obj.created_at}

@extend_schema(tags=["Calculations"],request=CalculationRequestSerializer,responses={201:CalculationResponseSerializer})
class CalculationCreateView(APIView):
    permission_classes=[AllowAny]
    throttle_scope="calculations"
    def post(self,request):
        s=CalculationRequestSerializer(data=request.data); s.is_valid(raise_exception=True)
        start=time.perf_counter(); engine=get_engine()
        data,assumptions,warnings=build_engine_input(s.validated_data)
        result=engine.calculate(data)
        runtime=int((time.perf_counter()-start)*1000)
        token=secrets.token_urlsafe(24)
        safe_input = {}
        for key, value in s.validated_data.items():
            if isinstance(value, UUID):
                safe_input[key] = str(value)
            else:
                safe_input[key] = value
        obj=Calculation.objects.create(access_token_hash=_hash(token),status="completed",source_mode=s.validated_data["source_mode"],
                                       input_payload=safe_input,result_payload=result,assumptions=assumptions,warnings=warnings,
                                       algorithm_version=engine.version,runtime_ms=runtime)
        return Response(_response(obj,token),status=status.HTTP_201_CREATED)

@extend_schema(tags=["Calculations"],responses={200:CalculationResponseSerializer})
class CalculationDetailView(APIView):
    permission_classes=[AllowAny]
    def _check(self,request,obj):
        token=request.query_params.get("access_token") or request.headers.get("X-Calculation-Token")
        if not token or not secrets.compare_digest(_hash(token),obj.access_token_hash):
            raise PermissionDenied("A valid calculation access token is required.")
        return token
    def get(self,request,public_id):
        obj=get_object_or_404(Calculation,public_id=public_id); token=self._check(request,obj)
        return Response(_response(obj,token))
    def delete(self,request,public_id):
        obj=get_object_or_404(Calculation,public_id=public_id); self._check(request,obj); obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
