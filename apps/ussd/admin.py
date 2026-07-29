
from django.contrib import admin

from .models import (
    UssdMarketPrediction,
    UssdMarketRecommendation,
    UssdPriceAlert,
    UssdSubscriber,
)


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


@admin.register(UssdMarketPrediction)
class UssdMarketPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "market",
        "commodity",
        "pricetype",
        "period",
        "target_date",
        "predicted_price",
        "generated_at",
    )
    search_fields = ("market__name", "commodity", "pricetype", "period")
    list_filter = ("commodity", "pricetype", "period", "market")


@admin.register(UssdMarketRecommendation)
class UssdMarketRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "role",
        "commodity",
        "recommendation_type",
        "action",
        "target_date",
        "market",
        "period",
        "trend",
        "confidence",
    )
    search_fields = ("role", "commodity", "recommendation_type", "market__name")
    list_filter = ("role", "commodity", "recommendation_type", "action", "trend")
