from django.contrib import admin

from .models import Market, MarketCommodityPrice


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "admin_area", "status", "created_at", "deleted_at")
    list_filter = ("status", "admin_area")
    search_fields = ("name", "code", "address")
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(MarketCommodityPrice)
class MarketCommodityPriceAdmin(admin.ModelAdmin):
    list_display = ("market", "commodity", "price", "currency", "price_date", "created_at", "deleted_at")
    list_filter = ("currency", "price_date", "market", "commodity")
    search_fields = ("market__name", "commodity__name")
    readonly_fields = ("public_id", "created_at", "updated_at")
