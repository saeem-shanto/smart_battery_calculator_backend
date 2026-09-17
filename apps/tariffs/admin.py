from django.contrib import admin
from .models import TariffPlan
@admin.register(TariffPlan)
class TariffPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "kind", "feed_in_rate", "is_active", "updated_at")
    list_filter = ("kind", "is_active", "provider")
    search_fields = ("name", "provider")
