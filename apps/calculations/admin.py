from django.contrib import admin
from .models import Calculation
@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display=("public_id","status","source_mode","algorithm_version","runtime_ms","created_at")
    list_filter=("status","source_mode","algorithm_version")
    search_fields=("public_id",)
    readonly_fields=("public_id","access_token_hash","created_at","updated_at")
