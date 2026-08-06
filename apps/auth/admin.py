from django.contrib import admin

from .models import EmailVerificationToken, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "public_id",
        "user",
        "get_roles",
        "phone_number",
        "organization",
        "farm_location",
        "farm_group",
        "email_verified_at",
        "created_at",
    )
    search_fields = (
        "public_id",
        "user__username",
        "user__email",
        "phone_number",
        "organization",
        "farm_location",
        "farm_group",
    )
    list_filter = ("roles", "email_verified_at")
    readonly_fields = ("public_id",)

    def get_roles(self, obj):
        return ", ".join([role.code for role in obj.roles.all()])
    get_roles.short_description = "Roles"


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    search_fields = ("user__username", "user__email", "token")
    list_filter = ("used_at", "expires_at", "created_at")
    readonly_fields = ("token", "created_at")
