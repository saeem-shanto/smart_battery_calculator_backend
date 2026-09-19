from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from drf_spectacular.utils import extend_schema_field

from apps.calculations.artifact_access import calculation_artifacts
from apps.calculations.models import Calculation
from apps.calculations.serializers import CalculationFileSerializer

from .models import UserProfile

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar_download_path = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "name",
            "is_staff",
            "avatar_download_path",
        ]
        read_only_fields = fields

    def get_name(self, obj) -> str:
        return obj.get_full_name().strip() or obj.get_username()

    def get_avatar_download_path(self, obj) -> str | None:
        try:
            profile = obj.battery_profile
        except UserProfile.DoesNotExist:
            return None
        if not profile.avatar or not profile.avatar.name:
            return None
        return "/api/v1/accounts/me/avatar/"




class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer()


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(min_length=3, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=254)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        validate_password(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        try:
            with transaction.atomic():
                user = User.objects.create_user(password=password, **validated_data)
                UserProfile.objects.create(user=user)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"username": "That username is already in use."}
            ) from exc
        return user


class UserTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }
        request = self.context.get("request")
        user = authenticate(request=request, **authenticate_kwargs)
        if user is None:
            raise AuthenticationFailed("No active account was found with the given credentials.")
        UserProfile.objects.get_or_create(user=user)
        self.user = user
        refresh = self.get_token(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSummarySerializer(user).data,
        }


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "avatar"]
        extra_kwargs = {
            "username": {"required": False},
            "email": {"required": False, "allow_blank": True},
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
        }

    def validate_username(self, value):
        value = value.strip()
        qs = User.objects.filter(username__iexact=value).exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def validate_avatar(self, value):
        if value is None:
            return value
        max_bytes = settings.PROFILE_AVATAR_MAX_MB * 1024 * 1024
        if getattr(value, "size", 0) > max_bytes:
            raise serializers.ValidationError(
                f"Profile picture must be {settings.PROFILE_AVATAR_MAX_MB} MB or smaller."
            )
        content_type = (getattr(value, "content_type", "") or "").lower()
        if content_type and content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise serializers.ValidationError("Profile picture must be JPEG, PNG, or WebP.")
        return value

    def update(self, instance, validated_data):
        avatar_marker = object()
        avatar = validated_data.pop("avatar", avatar_marker)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        try:
            instance.save()
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"username": "That username is already in use."}
            ) from exc
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if avatar is not avatar_marker:
            if avatar is None:
                profile.avatar = ""
            else:
                profile.avatar = avatar
            profile.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class OwnedCalculationListSerializer(serializers.ModelSerializer):
    input_filename = serializers.SerializerMethodField()
    result = serializers.JSONField(source="result_payload")
    files = serializers.SerializerMethodField()

    class Meta:
        model = Calculation
        fields = [
            "public_id",
            "status",
            "postcode",
            "suburb",
            "state",
            "metadata",
            "input_filename",
            "result",
            "algorithm_version",
            "runtime_ms",
            "files",
            "created_at",
            "updated_at",
        ]

    def get_input_filename(self, obj) -> str | None:
        return (obj.input_payload or {}).get("original_filename") or (
            obj.input_file.canonical_filename if obj.input_file_id else None
        )

    @extend_schema_field(CalculationFileSerializer(many=True))
    def get_files(self, obj):
        return calculation_artifacts(obj)
