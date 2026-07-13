from django.db import models
from apps.common.ids import generate_unique_public_id
from django.conf import settings


class CommodityListing(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    commodity = models.ForeignKey(
        'commodities.Commodity',
        on_delete=models.CASCADE,
        related_name='listings'
    )
    adm_area = models.ForeignKey(
        'areas.AdmArea',
        on_delete=models.CASCADE,
        related_name='listings'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='listings',
        null=True,
        blank=True
    )
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "commodity_listings"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(CommodityListing)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Listing {self.public_id} - {self.commodity.name}"


class ListingImage(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    listing = models.ForeignKey(
        CommodityListing,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image_url = models.CharField(max_length=255)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "listings_images"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(ListingImage)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image {self.public_id} for Listing {self.listing.public_id}"
