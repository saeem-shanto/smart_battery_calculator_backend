from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.exceptions import AuthenticationFailed
from drf_spectacular.utils import extend_schema

class AdminTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        if not self.user.is_staff:
            raise AuthenticationFailed("Administrator access is required.")
        data["user"] = {"id": self.user.id, "username": self.user.get_username(), "email": self.user.email, "is_staff": True}
        return data

@extend_schema(tags=["Admin Authentication"])
class AdminTokenObtainPairView(TokenObtainPairView):
    serializer_class = AdminTokenObtainPairSerializer
