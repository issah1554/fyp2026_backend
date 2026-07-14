from django.db import models

from apps.auth.models import Profile
from apps.common.ids import generate_unique_public_id


class Permission(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    code = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "permissions"
        ordering = ["code"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(Permission)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class RolePermission(models.Model):
    role = models.CharField(max_length=32, choices=Profile.Role.choices)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="role_links")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_permissions"
        ordering = ["role", "permission__code"]
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission"),
        ]

    def __str__(self):
        return f"{self.role}: {self.permission.code}"
