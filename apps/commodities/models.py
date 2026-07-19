from django.conf import settings
from django.db import models

from apps.common.ids import generate_unique_public_id


class CommodityCategory(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "commodity categories"

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(CommodityCategory)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Market(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=150, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Market)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Commodity(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    categories = models.ManyToManyField(
        CommodityCategory,
        through="CommodityCategoryMap",
        related_name="commodities",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "commodities"

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Commodity)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CommodityCategoryMap(models.Model):
    commodity = models.ForeignKey(Commodity, on_delete=models.CASCADE)
    category = models.ForeignKey(CommodityCategory, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["commodity", "category"],
                name="unique_commodity_category_map",
            )
        ]

    def __str__(self):
        return f"{self.commodity} -> {self.category}"


class MarketPriceRecord(models.Model):
    class PriceType(models.TextChoices):
        RETAIL = "Retail", "Retail"
        WHOLESALE = "Wholesale", "Wholesale"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
    market = models.ForeignKey(
        Market,
        on_delete=models.PROTECT,
        related_name="price_records",
    )
    commodity = models.ForeignKey(
        Commodity,
        on_delete=models.PROTECT,
        related_name="price_records",
    )
    price_type = models.CharField(max_length=32, choices=PriceType.choices)
    unit = models.CharField(max_length=32)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=16, default="TZS")
    record_date = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="market_price_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-record_date", "market__name", "commodity__name"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(MarketPriceRecord)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.market} | {self.commodity} | {self.record_date}"
