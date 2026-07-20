from django.db import models

from apps.common.ids import generate_unique_public_id


class AdmArea(models.Model):
    class Level(models.TextChoices):
        REGION = "region", "Region"
        DISTRICT = "district", "District"
        WARD = "ward", "Ward"

    public_id = models.CharField(max_length=10, unique=True, editable=False)
    name = models.CharField(max_length=150)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    level = models.CharField(
        max_length=50,
        choices=Level.choices,
        default=Level.REGION,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adm_areas"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["parent", "level", "name"], name="adm_areas_path_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["parent", "level", "name"], name="adm_areas_parent_level_name_uniq"),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(AdmArea)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.level})"
