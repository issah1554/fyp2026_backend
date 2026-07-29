from django.conf import settings
from django.db import models

from apps.common.ids import generate_unique_public_id
from apps.commodities.models import Market


class UssdSubscriber(models.Model):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        ENTREPRENEUR = "entrepreneur", "Entrepreneur"
        BUYER = "buyer", "Buyer"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ussd_subscriber",
    )
    phone_number = models.CharField(max_length=32, unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=32, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(UssdSubscriber)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


class UssdPriceAlert(models.Model):
    class Commodity(models.TextChoices):
        MAIZE = "maize", "Maize"
        RICE = "rice", "Rice"

    subscriber = models.ForeignKey(
        UssdSubscriber,
        on_delete=models.CASCADE,
        related_name="price_alerts",
    )
    commodity = models.CharField(max_length=32, choices=Commodity.choices)
    target_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscriber", "commodity"],
                name="unique_ussd_price_alert_per_commodity",
            )
        ]

    def __str__(self):
        return f"{self.subscriber.phone_number} - {self.commodity}"


class UssdMarketPrediction(models.Model):
    class Commodity(models.TextChoices):
        BEANS = "Beans", "Beans"
        RICE = "Rice", "Rice"

    class PriceType(models.TextChoices):
        RETAIL = "Retail", "Retail"
        WHOLESALE = "Wholesale", "Wholesale"

    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        SEASONAL = "seasonal", "Seasonal"

    market = models.ForeignKey(
        Market,
        on_delete=models.CASCADE,
        related_name="ussd_predictions",
    )
    commodity = models.CharField(max_length=32, choices=Commodity.choices)
    pricetype = models.CharField(max_length=32, choices=PriceType.choices)
    unit = models.CharField(max_length=32)
    period = models.CharField(max_length=32, choices=Period.choices)
    target_date = models.DateField()
    period_end = models.DateField()
    season = models.CharField(max_length=64)
    predicted_price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=16, default="TZS")
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["market__name", "commodity", "pricetype", "period", "-target_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["market", "commodity", "pricetype", "period", "target_date"],
                name="unique_ussd_market_prediction_per_date",
            )
        ]

    def __str__(self):
        return (
            f"{self.market.name} | {self.commodity} | {self.pricetype} | "
            f"{self.period} | {self.target_date}"
        )


class UssdMarketRecommendation(models.Model):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        ENTREPRENEUR = "entrepreneur", "Entrepreneur"
        BUYER = "buyer", "Buyer"

    class RecommendationType(models.TextChoices):
        TIME = "time", "Time"
        MARKET = "market", "Market"

    class Action(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class Trend(models.TextChoices):
        RISING = "rising", "Rising"
        FALLING = "falling", "Falling"
        STABLE = "stable", "Stable"

    class Commodity(models.TextChoices):
        BEANS = "Beans", "Beans"
        RICE = "Rice", "Rice"

    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        SEASONAL = "seasonal", "Seasonal"

    role = models.CharField(max_length=32, choices=Role.choices)
    commodity = models.CharField(max_length=32, choices=Commodity.choices)
    recommendation_type = models.CharField(max_length=16, choices=RecommendationType.choices)
    action = models.CharField(max_length=16, choices=Action.choices)
    target_date = models.DateField()
    market = models.ForeignKey(
        Market,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ussd_recommendations",
    )
    period = models.CharField(max_length=32, choices=Period.choices, null=True, blank=True)
    window_start = models.DateField(null=True, blank=True)
    window_end = models.DateField(null=True, blank=True)
    season = models.CharField(max_length=64)
    trend = models.CharField(max_length=16, choices=Trend.choices)
    recommended_price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=16, default="TZS")
    confidence = models.DecimalField(max_digits=5, decimal_places=2)
    summary = models.CharField(max_length=255)
    reason = models.TextField()
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["role", "commodity", "recommendation_type", "-target_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["role", "commodity", "recommendation_type", "target_date"],
                name="unique_ussd_market_recommendation_per_date",
            )
        ]

    def __str__(self):
        return (
            f"{self.role} | {self.commodity} | {self.recommendation_type} | "
            f"{self.target_date}"
        )
