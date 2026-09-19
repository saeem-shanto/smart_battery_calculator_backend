from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError, transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.calculations.artifact_access import calculation_artifacts
from apps.calculations.models import Calculation
from apps.calculations.serializers import CalculationFileSerializer

from .models import TwoFactorChallenge, UserProfile
from .security import (
    EmailDeliveryFailed,
    EmailSecurityUnavailable,
    create_two_factor_challenge,
)

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar_download_path = serializers.SerializerMethodField()
    two_factor_enabled = serializers.SerializerMethodField()

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
            "two_factor_enabled",
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

    def get_two_factor_enabled(self, obj) -> bool:
        try:
            return bool(obj.battery_profile.two_factor_enabled)
        except UserProfile.DoesNotExist:
            return False


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSummarySerializer()


class TwoFactorRequiredSerializer(serializers.Serializer):
    two_factor_required = serializers.BooleanField(default=True)
    challenge_id = serializers.UUIDField()
    expires_in = serializers.IntegerField()
    resend_after = serializers.IntegerField()
    masked_email = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    two_factor_required = serializers.BooleanField(required=False)
    challenge_id = serializers.UUIDField(required=False)
    expires_in = serializers.IntegerField(required=False)
    resend_after = serializers.IntegerField(required=False)
    masked_email = serializers.CharField(required=False)
    access = serializers.CharField(required=False)
    refresh = serializers.CharField(required=False)
    user = UserSummarySerializer(required=False)


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

    def validate_email(self, value):
        value = value.strip().lower()
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already associated with an account.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        candidate = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        try:
            validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        try:
            with transaction.atomic():
                user = User.objects.create_user(password=password, **validated_data)
                UserProfile.objects.create(user=user)
        except IntegrityError as exc:
            raise serializers.ValidationError({"username": "That username is already in use."}) from exc
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
        profile, _ = UserProfile.objects.get_or_create(user=user)
        self.user = user
        if profile.two_factor_enabled:
            if not user.email:
                raise serializers.ValidationError({"email": "Two-factor authentication requires an email address on this account."})
            try:
                challenge = create_two_factor_challenge(user, TwoFactorChallenge.Purpose.LOGIN_USER)
            except (EmailSecurityUnavailable, EmailDeliveryFailed) as exc:
                raise serializers.ValidationError({"non_field_errors": [str(exc)]}) from exc
            return {
                "two_factor_required": True,
                "challenge_id": challenge.challenge_id,
                "expires_in": challenge.expires_in,
                "resend_after": challenge.resend_after,
                "masked_email": challenge.masked_email,
            }
        refresh = self.get_token(user)
        return {
            "two_factor_required": False,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSummarySerializer(user).data,
        }


class TwoFactorVerifySerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.RegexField(r"^\d{6}$", trim_whitespace=True)


class TwoFactorResendSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()


class TwoFactorEnableStartSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not self.context["request"].user.email:
            raise serializers.ValidationError({"email": "Add an email address to your profile before enabling two-factor authentication."})
        return attrs


class TwoFactorEnableVerifySerializer(TwoFactorVerifySerializer):
    pass


class TwoFactorDisableSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value


class TwoFactorStatusSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    email = serializers.EmailField(allow_blank=True)
    masked_email = serializers.CharField(allow_blank=True)
    email_configured = serializers.BooleanField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, min_length=8, max_length=128, trim_whitespace=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "This password reset link is invalid or has expired."})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "This password reset link is invalid or has expired."})
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        attrs["user"] = user
        return attrs


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

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk)
        if value and qs.exists():
            raise serializers.ValidationError("That email address is already associated with an account.")
        profile, _ = UserProfile.objects.get_or_create(user=self.instance)
        current_email = (self.instance.email or "").strip().lower()
        if profile.two_factor_enabled and value != current_email:
            raise serializers.ValidationError(
                "Disable two-factor authentication before changing the account email, then re-enable it to verify the new address."
            )
        return value

    def validate_avatar(self, value):
        if value is None:
            return value
        max_bytes = settings.PROFILE_AVATAR_MAX_MB * 1024 * 1024
        if getattr(value, "size", 0) > max_bytes:
            raise serializers.ValidationError(f"Profile picture must be {settings.PROFILE_AVATAR_MAX_MB} MB or smaller.")
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
            raise serializers.ValidationError({"username": "That username is already in use."}) from exc
        profile, _ = UserProfile.objects.get_or_create(user=instance)
        if avatar is not avatar_marker:
            profile.avatar = "" if avatar is None else avatar
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
