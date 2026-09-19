from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import UserProfile
from apps.accounts.serializers import UserSummarySerializer


class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue JWTs only after staff status is verified.

    SimpleJWT's default serializer creates the refresh token before custom
    post-validation checks. Authenticating explicitly avoids recording an
    outstanding refresh token for a valid non-staff user who is denied admin
    access.
    """

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
        UserProfile.objects.get_or_create(user=user)
        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSummarySerializer(user).data,
        }


@extend_schema(tags=["Admin Authentication"])
class AdminTokenObtainPairView(TokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer
    throttle_scope = "auth"


@extend_schema(tags=["Admin Authentication"])
class AdminTokenRefreshView(TokenRefreshView):
    throttle_scope = "auth"
