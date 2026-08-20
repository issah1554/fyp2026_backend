from django.db import models
from django.utils import timezone

from apps.common.ids import generate_unique_public_id


class ActiveSourceManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class MarketIntegrationSource(models.Model):
    class SourceType(models.TextChoices):
        INTERNAL = "internal", "Internal"
        API = "api", "API"
        SCRAPER = "scraper", "Scraper"
        FILE = "file", "File"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
    key = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.API)
    base_url = models.URLField(max_length=500, blank=True)
    prices_path = models.CharField(max_length=255, default="/api/prices", blank=True)
    health_path = models.CharField(max_length=255, default="/api/health", blank=True)
    sync_interval_hours = models.PositiveIntegerField(default=6, help_text="Number of hours to wait between automatic synchronizations.")
    is_active = models.BooleanField(default=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_imported_at = models.DateTimeField(null=True, blank=True)
    last_seen_record_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = ActiveSourceManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "market_integration_sources"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["key"], name="mis_key_idx"),
            models.Index(fields=["is_active", "deleted_at"], name="mis_active_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(MarketIntegrationSource)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.is_active = False
        self.save(update_fields=["deleted_at", "is_active", "updated_at"])

    def url(self, path):
        if not self.base_url:
            return ""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def __str__(self):
        return self.name
