from django.contrib import admin

from .models import TwoFactorChallenge, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_is_verified", "two_factor_enabled", "has_avatar", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("verified_email", "email_verified_at", "created_at", "updated_at")

    @admin.display(boolean=True, description="Email verified")
    def email_is_verified(self, obj):
        return bool(obj.user.email and obj.verified_email.strip().lower() == obj.user.email.strip().lower())

    @admin.display(boolean=True)
    def has_avatar(self, obj):
        return bool(obj.avatar and obj.avatar.name)


@admin.register(TwoFactorChallenge)
class TwoFactorChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "purpose", "attempts", "expires_at", "consumed_at", "created_at")
    list_filter = ("purpose", "consumed_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("id", "user", "purpose", "code_digest", "expires_at", "last_sent_at", "attempts", "consumed_at", "created_at")

    def has_add_permission(self, request):
        return False
