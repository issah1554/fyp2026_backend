from django.db import models
from apps.common.ids import generate_unique_public_id
from django.conf import settings
from apps.listings.models import CommodityListing

class Order(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    listing = models.ForeignKey(
        CommodityListing,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
        null=True,
        blank=True
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Order)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.public_id} - {self.status}"
