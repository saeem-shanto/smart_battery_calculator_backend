from django.contrib import admin
from .models import ProfileUpload
@admin.register(ProfileUpload)
class ProfileUploadAdmin(admin.ModelAdmin):
    list_display=("original_name","role","detected_format","interval_minutes","row_count","created_at","expires_at")
    readonly_fields=("parsed_payload","warnings","created_at")
