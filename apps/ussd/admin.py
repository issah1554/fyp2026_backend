
from django.contrib import admin

from .models import UssdPriceAlert, UssdSubscriber


@admin.register(UssdSubscriber)
class UssdSubscriberAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone_number", "role", "created_at")
    search_fields = ("full_name", "phone_number")
    list_filter = ("role",)


@admin.register(UssdPriceAlert)
class UssdPriceAlertAdmin(admin.ModelAdmin):
    list_display = ("subscriber", "commodity", "target_price", "is_active", "updated_at")
    search_fields = ("subscriber__full_name", "subscriber__phone_number")
    list_filter = ("commodity", "is_active")
