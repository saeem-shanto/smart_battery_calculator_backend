from django.contrib import admin
from django.db.models import Count
from io import BytesIO

from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from .artifact_access import artifact_exists
from .models import Calculation, StoredCsvResult, StoredInputFile


@admin.register(Calculation)
class CalculationAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "owner",
        "postcode",
        "location",
        "status",
        "input_filename",
        "has_input_file",
        "has_csv_file",
        "optimal_battery_kwh",
        "net_payment_aud",
        "runtime_ms",
        "created_at",
    )
    list_filter = ("status", "state", "algorithm_version", "created_at")
    search_fields = (
        "public_id",
        "postcode",
        "suburb",
        "state",
        "input_payload__original_filename",
        "input_payload__input_sha256",
        "input_file__sha256",
        "input_file__canonical_filename",
        "csv_result__sha256",
        "owner__username",
        "owner__email",
    )
    list_select_related = ("owner", "input_file", "csv_result")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # Record/location fields stay editable for admin corrections. Algorithm and
    # audit fields remain read-only.
    readonly_fields = (
        "id",
        "public_id",
        "access_token_hash",
        "owner",
        "input_file",
        "csv_result",
        "status",
        "source_mode",
        "input_payload",
        "result_payload",
        "assumptions",
        "warnings",
        "algorithm_version",
        "runtime_ms",
        "error_code",
        "error_message",
        "input_download_link",
        "csv_download_link",
        "created_at",
        "updated_at",
    )
    fields = (
        "public_id",
        "owner",
        "postcode",
        "suburb",
        "state",
        "metadata",
        "status",
        "source_mode",
        "input_file",
        "csv_result",
        "input_download_link",
        "csv_download_link",
        "input_payload",
        "result_payload",
        "assumptions",
        "warnings",
        "algorithm_version",
        "runtime_ms",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
        "access_token_hash",
    )

    @admin.display(description="Location")
    def location(self, obj):
        return ", ".join(x for x in [obj.suburb, obj.state] if x) or "-"

    @admin.display(description="Input filename")
    def input_filename(self, obj):
        return (obj.input_payload or {}).get("original_filename", "-")

    @admin.display(boolean=True, description="Input")
    def has_input_file(self, obj):
        return bool(obj.input_file_id and artifact_exists(obj.input_file))

    @admin.display(boolean=True, description="CSV")
    def has_csv_file(self, obj):
        return bool(obj.csv_result_id and artifact_exists(obj.csv_result))

    @admin.display(description="Battery kWh")
    def optimal_battery_kwh(self, obj):
        value = (obj.result_payload or {}).get("optimal_battery_size_kwh")
        return "-" if value is None else value

    @admin.display(description="Net payment AUD")
    def net_payment_aud(self, obj):
        value = (obj.result_payload or {}).get("net_annual_payment_aud")
        return "-" if value is None else value

    @admin.display(description="Input download")
    def input_download_link(self, obj):
        if not obj.input_file_id:
            return "File deleted"
        url = reverse("admin:calculations_storedinputfile_download", args=[obj.input_file_id])
        return format_html('<a href="{}">Download input</a>', url)

    @admin.display(description="CSV download")
    def csv_download_link(self, obj):
        if not obj.csv_result_id:
            return "File deleted / unavailable"
        url = reverse("admin:calculations_storedcsvresult_download", args=[obj.csv_result_id])
        return format_html('<a href="{}">Download CSV</a>', url)


@admin.register(StoredInputFile)
class StoredInputFileAdmin(admin.ModelAdmin):
    list_display = (
        "canonical_filename",
        "short_sha256",
        "size_bytes",
        "row_count",
        "calculation_count",
        "has_csv",
        "created_at",
        "download_link",
    )
    search_fields = ("canonical_filename", "sha256")
    list_filter = ("detected_format", "created_at")
    readonly_fields = (
        "id",
        "sha256",
        "canonical_filename",
        "content_type",
        "size_bytes",
        "storage_file",
        "detected_format",
        "row_count",
        "parsing_warnings",
        "download_link",
        "created_at",
        "updated_at",
    )
    exclude = ("data",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_calculation_count=Count("calculations"))

    @admin.display(description="SHA-256")
    def short_sha256(self, obj):
        return f"{obj.sha256[:12]}..."

    @admin.display(description="Calculations")
    def calculation_count(self, obj):
        return obj._calculation_count

    @admin.display(boolean=True, description="CSV linked")
    def has_csv(self, obj):
        return StoredCsvResult.objects.filter(input_file_id=obj.id).exists()

    @admin.display(description="Download")
    def download_link(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:calculations_storedinputfile_download", args=[obj.pk])
        return format_html('<a href="{}">Download input</a>', url)

    def get_urls(self):
        custom = [
            path(
                "<uuid:object_id>/download/",
                self.admin_site.admin_view(self.download_view),
                name="calculations_storedinputfile_download",
            )
        ]
        return custom + super().get_urls()

    def download_view(self, request, object_id):
        obj = get_object_or_404(StoredInputFile, pk=object_id)
        if obj.storage_file and obj.storage_file.name:
            try:
                obj.storage_file.open("rb")
                file_obj = obj.storage_file
            except Exception as exc:
                raise Http404 from exc
        elif obj.data is not None:
            file_obj = BytesIO(bytes(obj.data))
        else:
            raise Http404
        response = FileResponse(file_obj, as_attachment=True, filename=obj.canonical_filename, content_type=obj.content_type)
        response["Content-Length"] = str(obj.size_bytes)
        response["Cache-Control"] = "private, no-store"
        return response


@admin.register(StoredCsvResult)
class StoredCsvResultAdmin(admin.ModelAdmin):
    list_display = (
        "filename",
        "short_source_sha256",
        "input_file",
        "calculation_count",
        "short_sha256",
        "size_bytes",
        "engine_version",
        "runtime_ms",
        "created_at",
        "download_link",
    )
    search_fields = (
        "filename",
        "sha256",
        "source_input_sha256",
        "input_file__sha256",
        "input_file__canonical_filename",
    )
    list_filter = ("engine_version", "created_at")
    readonly_fields = (
        "id",
        "input_file",
        "source_input_sha256",
        "filename",
        "content_type",
        "size_bytes",
        "sha256",
        "storage_file",
        "result_payload",
        "engine_version",
        "algorithm_sha256",
        "runtime_ms",
        "download_link",
        "created_at",
    )
    exclude = ("data",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_calculation_count=Count("calculations"))

    @admin.display(description="Source SHA-256")
    def short_source_sha256(self, obj):
        return f"{obj.source_input_sha256[:12]}..."

    @admin.display(description="SHA-256")
    def short_sha256(self, obj):
        return f"{obj.sha256[:12]}..."

    @admin.display(description="Calculations")
    def calculation_count(self, obj):
        return obj._calculation_count

    @admin.display(description="Download")
    def download_link(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:calculations_storedcsvresult_download", args=[obj.pk])
        return format_html('<a href="{}">Download CSV</a>', url)

    def get_urls(self):
        custom = [
            path(
                "<uuid:object_id>/download/",
                self.admin_site.admin_view(self.download_view),
                name="calculations_storedcsvresult_download",
            )
        ]
        return custom + super().get_urls()

    def download_view(self, request, object_id):
        obj = get_object_or_404(StoredCsvResult, pk=object_id)
        if obj.storage_file and obj.storage_file.name:
            try:
                obj.storage_file.open("rb")
                file_obj = obj.storage_file
            except Exception as exc:
                raise Http404 from exc
        elif obj.data is not None:
            file_obj = BytesIO(bytes(obj.data))
        else:
            raise Http404
        response = FileResponse(file_obj, as_attachment=True, filename=obj.filename, content_type=obj.content_type)
        response["Content-Length"] = str(obj.size_bytes)
        response["Cache-Control"] = "private, no-store"
        return response
