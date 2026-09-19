from __future__ import annotations

import mimetypes

from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.calculations.models import Calculation
from apps.common.api_serializers import ApiErrorSerializer

from .models import TwoFactorChallenge, UserProfile
from .security import (
    EmailDeliveryFailed,
    EmailSecurityUnavailable,
    create_two_factor_challenge,
    email_security_available,
    mask_email,
    resend_two_factor_challenge,
    send_password_reset_email,
    verify_two_factor_challenge,
)
from .serializers import (
    AuthResponseSerializer,
    LoginResponseSerializer,
    LogoutSerializer,
    OwnedCalculationListSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    TwoFactorDisableSerializer,
    TwoFactorEnableStartSerializer,
    TwoFactorEnableVerifySerializer,
    TwoFactorRequiredSerializer,
    TwoFactorResendSerializer,
    TwoFactorStatusSerializer,
    TwoFactorVerifySerializer,
    UserProfileUpdateSerializer,
    UserSummarySerializer,
    UserTokenObtainPairSerializer,
)

User = get_user_model()


class EmailServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Email security service is temporarily unavailable. Please try again later."
    default_code = "email_unavailable"


def _auth_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        "two_factor_required": False,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": UserSummarySerializer(user).data,
    }


def _challenge_payload(challenge):
    return {
        "two_factor_required": True,
        "challenge_id": challenge.challenge_id,
        "expires_in": challenge.expires_in,
        "resend_after": challenge.resend_after,
        "masked_email": challenge.masked_email,
    }


def _blacklist_all_tokens(user) -> None:
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "registration"

    @extend_schema(tags=["User Accounts"], request=RegisterSerializer, responses={201: AuthResponseSerializer, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


@extend_schema(tags=["User Accounts"], responses={200: LoginResponseSerializer})
class UserTokenObtainPairView(TokenObtainPairView):
    serializer_class = UserTokenObtainPairSerializer
    throttle_scope = "auth"


@extend_schema(tags=["User Accounts"])
class UserTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"


class TwoFactorVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "two_factor"

    @extend_schema(tags=["User Accounts"], request=TwoFactorVerifySerializer, responses={200: AuthResponseSerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = verify_two_factor_challenge(
                str(serializer.validated_data["challenge_id"]),
                serializer.validated_data["code"],
                {TwoFactorChallenge.Purpose.LOGIN_USER, TwoFactorChallenge.Purpose.LOGIN_ADMIN},
            )
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This verification challenge was not found. Please sign in again.") from exc
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError({"code": [str(exc)]}) from exc

        if challenge.purpose == TwoFactorChallenge.Purpose.LOGIN_ADMIN and not challenge.user.is_staff:
            raise PermissionDenied("Administrator access is required.")
        return Response(_auth_payload(challenge.user))


class TwoFactorResendView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "two_factor"

    @extend_schema(tags=["User Accounts"], request=TwoFactorResendSerializer, responses={200: TwoFactorRequiredSerializer, 400: ApiErrorSerializer, 404: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = resend_two_factor_challenge(str(serializer.validated_data["challenge_id"]))
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This verification challenge was not found. Please sign in again.") from exc
        except RuntimeError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc
        except ValueError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response(_challenge_payload(challenge))


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(tags=["User Accounts"], responses={200: UserSummarySerializer}, operation_id="account_profile_retrieve")
    def get(self, request):
        UserProfile.objects.get_or_create(user=request.user)
        return Response(UserSummarySerializer(request.user).data)

    @extend_schema(tags=["User Accounts"], request=UserProfileUpdateSerializer, responses={200: UserSummarySerializer, 400: ApiErrorSerializer}, operation_id="account_profile_update")
    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSummarySerializer(user).data)


class TwoFactorStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["User Accounts"], responses={200: TwoFactorStatusSerializer})
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response({
            "enabled": profile.two_factor_enabled,
            "email": request.user.email or "",
            "masked_email": mask_email(request.user.email) if request.user.email else "",
            "email_configured": email_security_available(),
        })


class TwoFactorEnableStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "two_factor"

    @extend_schema(tags=["User Accounts"], request=TwoFactorEnableStartSerializer, responses={200: TwoFactorRequiredSerializer, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorEnableStartSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if profile.two_factor_enabled:
            raise ValidationError({"non_field_errors": ["Two-factor authentication is already enabled."]})
        try:
            challenge = create_two_factor_challenge(request.user, TwoFactorChallenge.Purpose.ENABLE)
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response(_challenge_payload(challenge))


class TwoFactorEnableVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "two_factor"

    @extend_schema(tags=["User Accounts"], request=TwoFactorEnableVerifySerializer, responses={200: UserSummarySerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorEnableVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = verify_two_factor_challenge(
                str(serializer.validated_data["challenge_id"]),
                serializer.validated_data["code"],
                {TwoFactorChallenge.Purpose.ENABLE},
            )
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This verification challenge was not found. Please start again.") from exc
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError({"code": [str(exc)]}) from exc
        if challenge.user_id != request.user.id:
            raise PermissionDenied("This verification challenge belongs to another account.")
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.two_factor_enabled = True
        profile.save(update_fields=["two_factor_enabled", "updated_at"])
        return Response(UserSummarySerializer(request.user).data)


class TwoFactorDisableView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "two_factor"

    @extend_schema(tags=["User Accounts"], request=TwoFactorDisableSerializer, responses={200: UserSummarySerializer, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorDisableSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.two_factor_enabled = False
        profile.save(update_fields=["two_factor_enabled", "updated_at"])
        TwoFactorChallenge.objects.filter(
            user=request.user,
            consumed_at__isnull=True,
        ).update(consumed_at=timezone.now())
        return Response(UserSummarySerializer(request.user).data)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(tags=["User Accounts"], request=PasswordResetRequestSerializer, responses={200: OpenApiResponse(description="Generic reset-email response."), 503: ApiErrorSerializer})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not email_security_available():
            raise EmailServiceUnavailable()
        email = serializer.validated_data["email"].strip()
        users = list(User.objects.filter(email__iexact=email, is_active=True).order_by("pk"))
        try:
            for user in users:
                send_password_reset_email(user)
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response({
            "detail": "If an active account uses that email address, a password reset link has been sent.",
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(tags=["User Accounts"], request=PasswordResetConfirmSerializer, responses={204: None, 400: ApiErrorSerializer})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        _blacklist_all_tokens(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvatarDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["User Accounts"], summary="Download the authenticated user's profile picture", responses={200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Profile image."), 404: ApiErrorSerializer})
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
        _blacklist_all_tokens(request.user)
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
