from django.contrib import admin

from .models import AdmArea


@admin.register(AdmArea)
class AdmAreaAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "parent", "public_id")
    search_fields = ("name", "public_id")
    list_filter = ("level",)
