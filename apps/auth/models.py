from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.ids import generate_unique_public_id


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
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    role = models.CharField(
        max_length=32,
        choices=Role.choices,
        default=Role.FARMER,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def mark_email_verified(self):
        if self.email_verified_at is None:
            self.email_verified_at = timezone.now()
            self.save(update_fields=["email_verified_at", "updated_at"])

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Profile)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    class Meta:
        db_table = "users_profiles"

    def __str__(self):
        return f"{self.user.username} profile"


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_tokens",
    )
    token = models.CharField(max_length=96, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "email_verification_tokens"
        ordering = ["-created_at"]

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def mark_used(self):
        if self.used_at is None:
            self.used_at = timezone.now()
            self.save(update_fields=["used_at"])

    def __str__(self):
        return f"Email verification token for {self.user}"
