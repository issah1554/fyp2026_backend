from django.contrib import admin

from .models import MarketIntegrationSource


@admin.register(MarketIntegrationSource)
class MarketIntegrationSourceAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "name",
        "source_type",
        "is_active",
        "base_url",
        "last_checked_at",
        "last_imported_at",
        "last_seen_record_at",
    )
    list_filter = ("source_type", "is_active", "deleted_at")
    search_fields = ("key", "name", "base_url")
    readonly_fields = ("public_id", "created_at", "updated_at", "deleted_at")
