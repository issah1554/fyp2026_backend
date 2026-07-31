from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.areas.models import AdmArea
from apps.common.ids import generate_unique_public_id


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Market(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, blank=True)
    admin_area = models.ForeignKey(
        AdmArea,
        on_delete=models.PROTECT,
        related_name="markets",
    )
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=50, default="active")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_markets",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_markets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "markets"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Market)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def __str__(self):
        return self.name


class MarketCommodityPrice(models.Model):
    class Currency(models.TextChoices):
        USD = "USD", "USD"
        TZS = "TZS", "TZS"

    class PriceType(models.TextChoices):
        RETAIL = "retail", "retail"
        WHOLESALE = "wholesale", "wholesale"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
    market = models.ForeignKey(
        Market,
        on_delete=models.CASCADE,
        related_name="commodity_prices",
    )
    commodity = models.ForeignKey(
        "commodities.Commodity",
        on_delete=models.CASCADE,
        related_name="market_prices",
    )
    price_type = models.CharField(
        max_length=32,
        choices=PriceType.choices,
        null=True,
        blank=True,
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    min_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.TZS,
    )
    source_key = models.CharField(max_length=50, blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    price_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_market_commodity_prices",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_market_commodity_prices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "commodities_prices"
        ordering = ["-price_date", "market__name", "commodity__name"]
        indexes = [
            models.Index(fields=["market", "price_date"], name="mcp_market_date_idx"),
            models.Index(fields=["commodity", "price_date"], name="mcp_commodity_date_idx"),
            models.Index(fields=["source_key", "commodity"], name="mcp_source_commodity_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["market", "commodity", "price_date", "price_type"],
                condition=models.Q(deleted_at__isnull=True),
                name="market_commodity_price_unique",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(MarketCommodityPrice)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def __str__(self):
        if self.price_type:
            return f"{self.commodity} ({self.price_type}) at {self.market} on {self.price_date}"
        return f"{self.commodity} at {self.market} on {self.price_date}"
