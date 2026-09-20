from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.exceptions import EmailServiceUnavailable, ResendCooldown
from apps.accounts.models import TwoFactorChallenge, UserProfile
from apps.accounts.security import EmailCooldownActive, EmailDeliveryFailed, EmailSecurityUnavailable, create_two_factor_challenge
from apps.accounts.serializers import LoginResponseSerializer, UserSummarySerializer
from apps.common.api_serializers import ApiErrorSerializer


class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue admin JWTs only after staff status and optional email OTP are verified."""

    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }
        request = self.context.get("request")
        user = authenticate(request=request, **authenticate_kwargs)
        if user is None:
            raise AuthenticationFailed("No active account was found with the given credentials.")
        if not user.is_staff:
            raise AuthenticationFailed("Administrator access is required.")

        self.user = user
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.two_factor_enabled:
            if not user.email:
                raise serializers.ValidationError({"email": "Two-factor authentication requires an email address on this account."})
            try:
                challenge = create_two_factor_challenge(user, TwoFactorChallenge.Purpose.LOGIN_ADMIN)
            except EmailCooldownActive as exc:
                raise ResendCooldown(
                    exc.retry_after_seconds,
                    exc.available_at,
                    code="two_factor_send_cooldown",
                ) from exc
            except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
                raise EmailServiceUnavailable(str(exc)) from exc
            return {
                "two_factor_required": True,
                "challenge_id": challenge.challenge_id,
                "expires_in": challenge.expires_in,
                "resend_after": challenge.resend_after,
                "resend_available_in": challenge.resend_after,
                "resend_available_at": challenge.resend_available_at,
                "masked_email": challenge.masked_email,
            }

        refresh = self.get_token(user)
        return {
            "two_factor_required": False,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSummarySerializer(user).data,
        }


@extend_schema(
    tags=["Admin Authentication"],
    responses={
        200: LoginResponseSerializer,
        400: ApiErrorSerializer,
        401: ApiErrorSerializer,
        429: ApiErrorSerializer,
        503: ApiErrorSerializer,
    },
)
class AdminTokenObtainPairView(TokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer
    throttle_scope = "auth"


@extend_schema(tags=["Admin Authentication"])
class AdminTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"
