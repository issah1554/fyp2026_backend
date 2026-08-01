from django.contrib import admin
from django.contrib import messages

from apps.market_integrations.services import sync_prices, check_viwanda_updates
from .models import Market, MarketCommodityPrice


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "admin_area", "status", "created_at", "deleted_at")
    list_filter = ("status", "admin_area")
    search_fields = ("name", "code", "address")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(MarketCommodityPrice)
class MarketCommodityPriceAdmin(admin.ModelAdmin):
    list_display = (
        "market",
        "commodity",
        "price_type",
        "price",
        "min_price",
        "max_price",
        "currency",
        "price_date",
        "created_at",
        "deleted_at",
    )
    list_filter = ("price_type", "currency", "price_date", "market", "commodity")
    search_fields = ("market__name", "commodity__name")
    readonly_fields = ("public_id", "created_at", "updated_at")
    actions = ["sync_all_sources", "check_viwanda_updates_action"]

    @admin.action(description="Sync all market integration sources")
    def sync_all_sources(self, request, queryset):
        try:
            result = sync_prices()
            self.message_user(
                request,
                f"Successfully synced market integrations: {result['created']} created, {result['updated']} updated.",
                messages.SUCCESS
            )
            for error in result["errors"]:
                self.message_user(request, f"Error syncing {error['source']}: {error['error']}", messages.WARNING)
        except Exception as e:
            self.message_user(request, f"Error syncing: {e}", messages.ERROR)

    @admin.action(description="Check for updates from viwanda.go.tz")
    def check_viwanda_updates_action(self, request, queryset):
        try:
            result = check_viwanda_updates()
            self.message_user(
                request,
                f"Successfully checked for updates. Downloaded {result['downloaded_count']} new files. "
                f"Synced: {result['sync_result']['created']} created, {result['sync_result']['updated']} updated.",
                messages.SUCCESS
            )
            for error in result["sync_result"]["errors"]:
                self.message_user(request, f"Error syncing {error['source']}: {error['error']}", messages.WARNING)
        except Exception as e:
            self.message_user(request, f"Error checking for updates: {e}", messages.ERROR)
