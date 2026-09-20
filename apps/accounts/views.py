from __future__ import annotations

import mimetypes

from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
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

from .exceptions import AccountEmailNotFound, EmailServiceUnavailable
from .models import TwoFactorChallenge, UserProfile
from .security import (
    EmailDeliveryFailed,
    EmailSecurityUnavailable,
    create_two_factor_challenge,
    email_security_available,
    is_user_email_verified,
    mask_email,
    normalize_email,
    resend_two_factor_challenge,
    send_password_reset_email,
    verify_two_factor_challenge,
)
from .serializers import (
    AuthResponseSerializer,
    EmailVerificationChallengeSerializer,
    EmailVerificationResendSerializer,
    EmailVerificationStatusSerializer,
    EmailVerificationVerifySerializer,
    LoginResponseSerializer,
    LogoutSerializer,
    OwnedCalculationListSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestResponseSerializer,
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


def _email_verification_payload(challenge):
    return {
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

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_register",
        summary="Register an optional user account",
        description=(
            "Creates an account and immediately issues JWTs. Email is optional and, when supplied, "
            "does not need to be verified before normal sign-in or application use."
        ),
        request=RegisterSerializer,
        responses={201: AuthResponseSerializer, 400: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(_auth_payload(user), status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["User Accounts"],
    responses={
        200: LoginResponseSerializer,
        400: ApiErrorSerializer,
        401: ApiErrorSerializer,
        503: ApiErrorSerializer,
    },
)
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

    @extend_schema(tags=["User Accounts"], request=TwoFactorResendSerializer, responses={200: TwoFactorRequiredSerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer, 503: ApiErrorSerializer})
    def post(self, request):
        serializer = TwoFactorResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge_id = str(serializer.validated_data["challenge_id"])
        try:
            existing = TwoFactorChallenge.objects.get(pk=challenge_id)
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This verification challenge was not found. Please sign in again.") from exc
        if existing.purpose == TwoFactorChallenge.Purpose.VERIFY_EMAIL:
            raise PermissionDenied("Use the authenticated email-verification resend endpoint for this challenge.")
        try:
            challenge = resend_two_factor_challenge(challenge_id)
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

    @extend_schema(
        tags=["User Accounts"],
        responses={200: UserSummarySerializer},
        operation_id="account_profile_retrieve",
        summary="Get the current user profile",
        description="Includes optional email-verification and two-factor-authentication status.",
    )
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
            "email_verified": is_user_email_verified(request.user, profile),
            "email_configured": email_security_available(),
        })


class TwoFactorEnableStartView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "two_factor"

    @extend_schema(
        tags=["User Accounts"],
        request=TwoFactorEnableStartSerializer,
        responses={200: TwoFactorRequiredSerializer, 400: ApiErrorSerializer, 503: ApiErrorSerializer},
        summary="Start optional two-factor authentication setup",
        description=(
            "Requires the current password and sends an OTP to the current account email. "
            "Successfully verifying the setup OTP also marks that exact email address as verified."
        ),
    )
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

    @extend_schema(tags=["User Accounts"], request=TwoFactorEnableVerifySerializer, responses={200: UserSummarySerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer})
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
        current_email = normalize_email(request.user.email)
        target_email = normalize_email(challenge.target_email)
        if not current_email or current_email != target_email:
            raise ValidationError({
                "email": ["The account email changed after this verification code was issued. Start two-factor setup again."]
            })
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.two_factor_enabled = True
        profile.verified_email = current_email
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["two_factor_enabled", "verified_email", "email_verified_at", "updated_at"])
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


class EmailVerificationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_email_verification_status",
        summary="Get email verification status",
        description=(
            "Email verification is optional. Registration and normal sign-in do not require a verified email. "
            "This endpoint reports whether the authenticated user's current email address has been verified."
        ),
        responses={200: EmailVerificationStatusSerializer},
    )
    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        verified = is_user_email_verified(request.user, profile)
        return Response({
            "email": request.user.email or "",
            "masked_email": mask_email(request.user.email) if request.user.email else "",
            "verified": verified,
            "verified_at": profile.email_verified_at if verified else None,
            "email_configured": email_security_available(),
        })


class EmailVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "email_verification"

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_email_verification_request",
        summary="Send an email verification code",
        description=(
            "Sends a six-digit OTP to the authenticated user's current account email. "
            "Email verification is optional and may be completed later from account settings."
        ),
        request=None,
        responses={200: EmailVerificationChallengeSerializer, 400: ApiErrorSerializer, 503: ApiErrorSerializer},
    )
    def post(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        if not request.user.email:
            raise ValidationError({"email": ["Add an email address to your profile before requesting verification."]})
        if is_user_email_verified(request.user, profile):
            raise ValidationError({"email": ["This email address is already verified."]})
        try:
            challenge = create_two_factor_challenge(request.user, TwoFactorChallenge.Purpose.VERIFY_EMAIL)
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response(_email_verification_payload(challenge))


class EmailVerificationResendView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "email_verification"

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_email_verification_resend",
        summary="Resend an email verification code",
        request=EmailVerificationResendSerializer,
        responses={200: EmailVerificationChallengeSerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer, 503: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = EmailVerificationResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge_id = str(serializer.validated_data["challenge_id"])
        try:
            existing = TwoFactorChallenge.objects.get(pk=challenge_id)
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This email verification challenge was not found. Please start again.") from exc
        if existing.user_id != request.user.id or existing.purpose != TwoFactorChallenge.Purpose.VERIFY_EMAIL:
            raise PermissionDenied("This verification challenge is not valid for this account action.")
        try:
            challenge = resend_two_factor_challenge(challenge_id)
        except RuntimeError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc
        except ValueError as exc:
            raise ValidationError({"non_field_errors": [str(exc)]}) from exc
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response(_email_verification_payload(challenge))


class EmailVerificationVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_scope = "email_verification"

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_email_verification_verify",
        summary="Verify the account email",
        description="Verifies only the exact email address to which the OTP challenge was sent.",
        request=EmailVerificationVerifySerializer,
        responses={200: UserSummarySerializer, 400: ApiErrorSerializer, 403: ApiErrorSerializer, 404: ApiErrorSerializer},
    )
    def post(self, request):
        serializer = EmailVerificationVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            challenge = verify_two_factor_challenge(
                str(serializer.validated_data["challenge_id"]),
                serializer.validated_data["code"],
                {TwoFactorChallenge.Purpose.VERIFY_EMAIL},
            )
        except TwoFactorChallenge.DoesNotExist as exc:
            raise NotFound("This email verification challenge was not found. Please start again.") from exc
        except PermissionError as exc:
            raise PermissionDenied(str(exc)) from exc
        except ValueError as exc:
            raise ValidationError({"code": [str(exc)]}) from exc

        if challenge.user_id != request.user.id:
            raise PermissionDenied("This verification challenge belongs to another account.")
        current_email = normalize_email(request.user.email)
        target_email = normalize_email(challenge.target_email)
        if not current_email or current_email != target_email:
            raise ValidationError({
                "email": ["The account email changed after this verification code was issued. Request a new verification code."]
            })

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.verified_email = current_email
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["verified_email", "email_verified_at", "updated_at"])
        return Response(UserSummarySerializer(request.user).data)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["User Accounts"],
        operation_id="account_password_reset_request",
        summary="Request a password reset",
        description=(
            "Sends a password-reset email only when the submitted address belongs to an active account. "
            "Email verification is not required for password recovery. If no active account uses the address, "
            "the API returns 404 and no email is sent."
        ),
        request=PasswordResetRequestSerializer,
        responses={
            200: PasswordResetRequestResponseSerializer,
            400: ApiErrorSerializer,
            404: ApiErrorSerializer,
            503: ApiErrorSerializer,
        },
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).order_by("pk").first()
        if user is None:
            raise AccountEmailNotFound()
        if not email_security_available():
            raise EmailServiceUnavailable()
        try:
            send_password_reset_email(user)
        except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
            raise EmailServiceUnavailable(str(exc)) from exc
        return Response({"detail": "Password reset email sent."})


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
