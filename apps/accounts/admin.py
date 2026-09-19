from django.contrib import admin

from .models import TwoFactorChallenge, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "two_factor_enabled", "has_avatar", "created_at", "updated_at")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")

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
