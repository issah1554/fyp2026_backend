
from django.db import models

from apps.common.ids import generate_unique_public_id


class UssdSubscriber(models.Model):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        ENTREPRENEUR = "entrepreneur", "Entrepreneur"
        BUYER = "buyer", "Buyer"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
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
