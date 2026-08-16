from django.db import migrations

from apps.common.ids import generate_unique_public_id
from apps.users.system_permissions import SYSTEM_PERMISSIONS


def seed_system_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "Permission")
    RolePermission = apps.get_model("users", "RolePermission")

    permissions = []
    for code, name, description in SYSTEM_PERMISSIONS:
        permission = Permission.objects.filter(code=code).first()
        if permission is None:
            permission = Permission(
                public_id=generate_unique_public_id(Permission),
                code=code,
                name=name,
                description=description,
            )
            permission.save()
        else:
            permission.name = name
            permission.description = description
            permission.save(update_fields=["name", "description"])
        permissions.append(permission)

    RolePermission.objects.bulk_create(
        [RolePermission(role="admin", permission=permission) for permission in permissions],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_system_permissions, migrations.RunPython.noop),
    ]
