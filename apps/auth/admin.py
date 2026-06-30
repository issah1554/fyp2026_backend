from django.contrib import admin

from .models import EmailVerificationToken, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone_number", "organization", "email_verified_at", "created_at")
    search_fields = ("user__username", "user__email", "phone_number", "organization")
    list_filter = ("role", "email_verified_at")


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    search_fields = ("user__username", "user__email", "token")
    list_filter = ("used_at", "expires_at", "created_at")
    readonly_fields = ("token", "created_at")
