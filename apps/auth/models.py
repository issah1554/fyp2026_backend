from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.ids import generate_unique_public_id


def get_default_role_id():
    return None


class Profile(models.Model):
    class Role(models.TextChoices):
        FARMER = "farmer", "Farmer"
        ENTREPRENEUR = "entrepreneur", "Entrepreneur"
        BUYER = "buyer", "Buyer"
        MARKET_OFFICER = "market_officer", "Market Officer"
        ADMIN = "admin", "Administrator"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    roles = models.ManyToManyField(
        "users.Role",
        related_name="profiles",
        blank=True,
    )
    phone_number = models.CharField(max_length=32, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    farm_location = models.CharField(max_length=150, blank=True)
    farm_group = models.CharField(max_length=150, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __init__(self, *args, **kwargs):
        self._temp_role = kwargs.pop("role", None)
        super().__init__(*args, **kwargs)

    def has_role(self, role_code):
        return self.roles.filter(code=role_code).exists()

    def has_any_role(self, *role_codes):
        return self.roles.filter(code__in=role_codes).exists()

    @property
    def role(self):
        return self.roles.first()

    @role.setter
    def role(self, value):
        if not self.pk:
            self._temp_role = value
        else:
            self.roles.set([value] if value else [])

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def mark_email_verified(self):
        if self.email_verified_at is None:
            self.email_verified_at = timezone.now()
            self.save(update_fields=["email_verified_at", "updated_at"])

    def save(self, *args, **kwargs):
        # We need to temporarily remove role from update_fields if passed
        update_fields = kwargs.get("update_fields")
        has_role_in_fields = False
        if update_fields:
            update_fields = set(update_fields)
            if "role" in update_fields:
                update_fields.remove("role")
                has_role_in_fields = True
            kwargs["update_fields"] = update_fields

        if not self.public_id:
            self.public_id = generate_unique_public_id(Profile)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        
        super().save(*args, **kwargs)
        
        role_obj = getattr(self, "_temp_role", None)
        if role_obj is not None:
            if isinstance(role_obj, str):
                from apps.users.models import Role
                role_obj, _ = Role.objects.get_or_create(
                    code=role_obj,
                    defaults={
                        "public_id": generate_unique_public_id(Role),
                        "name": role_obj.replace("_", " ").title(),
                        "is_system": True,
                    }
                )
            self.roles.set([role_obj])
            self._temp_role = None
        elif has_role_in_fields and hasattr(self, "_temp_role") and self._temp_role is not None:
            role_obj = self._temp_role
            if isinstance(role_obj, str):
                from apps.users.models import Role
                role_obj, _ = Role.objects.get_or_create(
                    code=role_obj,
                    defaults={
                        "public_id": generate_unique_public_id(Role),
                        "name": role_obj.replace("_", " ").title(),
                        "is_system": True,
                    }
                )
            self.roles.set([role_obj])
            self._temp_role = None

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


class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token = models.CharField(max_length=96, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "password_reset_tokens"
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
        return f"Password reset token for {self.user}"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Profile)
def ensure_profile_default_role(sender, instance, created, **kwargs):
    if created:
        from apps.users.models import Role
        if not instance.roles.exists():
            default_role, _ = Role.objects.get_or_create(
                code=Profile.Role.FARMER,
                defaults={
                    "public_id": generate_unique_public_id(Role),
                    "name": "Farmer",
                    "description": "Commodity producer role.",
                    "is_system": True,
                },
            )
            instance.roles.add(default_role)

