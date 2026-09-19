from __future__ import annotations

import mimetypes

from django.http import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.api_serializers import ApiErrorSerializer
from apps.calculations.models import Calculation

from .models import UserProfile
from .serializers import (
    AuthResponseSerializer,
    LogoutSerializer,
    OwnedCalculationListSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    UserProfileUpdateSerializer,
    UserSummarySerializer,
    UserTokenObtainPairSerializer,
)


def _auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSummarySerializer(user).data,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "registration"

    @extend_schema(tags=["User Accounts"], request=RegisterSerializer, responses={201: AuthResponseSerializer, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


@extend_schema(tags=["User Accounts"])
class UserTokenObtainPairView(TokenObtainPairView):
    serializer_class = UserTokenObtainPairSerializer
    throttle_scope = "auth"


@extend_schema(tags=["User Accounts"])
class UserTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        tags=["User Accounts"],
        responses={200: UserSummarySerializer},
        operation_id="account_profile_retrieve",
    )
    def get(self, request):
        UserProfile.objects.get_or_create(user=request.user)
        return Response(UserSummarySerializer(request.user).data)

    @extend_schema(
        tags=["User Accounts"],
        request=UserProfileUpdateSerializer,
        responses={200: UserSummarySerializer, 400: ApiErrorSerializer},
        operation_id="account_profile_update",
    )
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSummarySerializer(user).data)


class AvatarDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["User Accounts"],
        summary="Download the authenticated user's profile picture",
        responses={200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Profile image."), 404: ApiErrorSerializer},
    )
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if not profile.avatar or not profile.avatar.name:
            raise Http404
        try:
            profile.avatar.open("rb")
        except Exception as exc:
            raise Http404 from exc
        content_type = mimetypes.guess_type(profile.avatar.name)[0] or "application/octet-stream"
        response = FileResponse(profile.avatar, content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        return response


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "auth"

    @extend_schema(tags=["User Accounts"], request=PasswordChangeSerializer, responses={204: None, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        for token in OutstandingToken.objects.filter(user=request.user):
            BlacklistedToken.objects.get_or_create(token=token)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    @extend_schema(tags=["User Accounts"], request=LogoutSerializer, responses={204: None, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["User Accounts"], responses={200: OwnedCalculationListSerializer(many=True)})
class MyCalculationsView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OwnedCalculationListSerializer

    def get_queryset(self):
        return (
            Calculation.objects.select_related("input_file", "csv_result")
            .filter(owner=self.request.user)
            .order_by("-created_at")
        )
