from django.contrib import admin

from .models import Commodity, CommodityCategory, CommodityCategoryMap, CommodityUnit


class CommodityCategoryMapInline(admin.TabularInline):
    model = CommodityCategoryMap
    extra = 1


@admin.register(CommodityCategory)
class CommodityCategoryAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "created_at")
    search_fields = ("public_id", "name", "description")
    readonly_fields = ("public_id", "created_at")


@admin.register(CommodityUnit)
class CommodityUnitAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "symbol", "created_at")
    search_fields = ("public_id", "name", "symbol", "description")
    readonly_fields = ("public_id", "created_at")


@admin.register(Commodity)
class CommodityAdmin(admin.ModelAdmin):
    list_display = ("public_id", "name", "unit", "unit_ref", "created_at")
    search_fields = ("public_id", "name", "unit", "unit_ref__name", "unit_ref__symbol", "description")
    readonly_fields = ("public_id", "created_at")
    inlines = [CommodityCategoryMapInline]


@admin.register(CommodityCategoryMap)
class CommodityCategoryMapAdmin(admin.ModelAdmin):
    list_display = ("commodity", "category", "created_at")
    search_fields = ("commodity__name", "category__name")
    readonly_fields = ("created_at",)
