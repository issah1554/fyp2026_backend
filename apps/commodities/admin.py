from django.contrib import admin

from .models import Commodity, CommodityCategory, CommodityCategoryMap, CommodityUnit, CommodityUnitMap


class CommodityCategoryMapInline(admin.TabularInline):
    model = CommodityCategoryMap
    extra = 1
    autocomplete_fields = ["category"]


class CommodityUnitMapInline(admin.TabularInline):
    model = CommodityUnitMap
    extra = 1
    autocomplete_fields = ["unit"]
    fields = ["unit", "is_primary", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(CommodityCategory)
class CommodityCategoryAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "created_at")
    search_fields = ("public_id", "name")
    readonly_fields = ("public_id", "created_at")


@admin.register(CommodityUnit)
class CommodityUnitAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "symbol", "created_at")
    search_fields = ("public_id", "name", "symbol")
    readonly_fields = ("public_id", "created_at")


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "get_primary_unit", "created_at")
    search_fields = ("public_id", "name", "unit_maps__unit__name", "unit_maps__unit__symbol")
    readonly_fields = ("public_id", "created_at")
    inlines = [CommodityUnitMapInline, CommodityCategoryMapInline]

    @admin.display(description="Primary Unit")
    def get_primary_unit(self, obj):
        mapping = obj.unit_maps.filter(is_primary=True).select_related("unit").first()
        if mapping is None:
            mapping = obj.unit_maps.select_related("unit").first()
        return mapping.unit.symbol if mapping else "—"


@admin.register(CommodityCategoryMap)
class CommodityCategoryMapAdmin(admin.ModelAdmin):
    list_display = ("commodity", "category", "created_at")
    search_fields = ("commodity__name", "category__name")
    readonly_fields = ("created_at",)


@admin.register(CommodityUnitMap)
class CommodityUnitMapAdmin(admin.ModelAdmin):
    list_display = ("commodity", "unit", "is_primary", "created_at")
    search_fields = ("commodity__name", "unit__name", "unit__symbol")
    list_filter = ("is_primary",)
    readonly_fields = ("created_at",)
