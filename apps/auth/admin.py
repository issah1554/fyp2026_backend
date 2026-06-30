from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "phone_number", "organization", "created_at")
    search_fields = ("user__username", "user__email", "phone_number", "organization")
    list_filter = ("role",)
