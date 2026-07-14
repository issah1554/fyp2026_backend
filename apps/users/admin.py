from django.contrib import admin

from .models import Permission, Role, RolePermission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("public_id", "code", "name", "created_at")
    search_fields = ("public_id", "code", "name", "description")
    readonly_fields = ("public_id", "created_at")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("public_id", "code", "name", "is_system", "created_at")
    list_filter = ("is_system",)
    search_fields = ("public_id", "code", "name", "description")
    readonly_fields = ("public_id", "created_at")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "created_at")
    list_filter = ("role",)
    search_fields = ("role", "permission__code", "permission__name")
    readonly_fields = ("created_at",)
