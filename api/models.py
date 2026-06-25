from django.conf import settings
from django.db import models


class Profile(models.Model):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        ENTREPRENEUR = "entrepreneur", "Entrepreneur"
        BUYER = "buyer", "Buyer"
        MARKET_OFFICER = "market_officer", "Market Officer"
        ADMIN = "admin", "Administrator"
        RESEARCHER = "researcher", "Researcher"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.FARMER,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} profile"
