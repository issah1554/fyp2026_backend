from django.db import migrations

from apps.common.ids import generate_unique_public_id
from apps.users.system_permissions import DEFAULT_ROLE_PERMISSIONS, SYSTEM_PERMISSIONS


def seed_endpoint_access_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "Permission")
    Role = apps.get_model("users", "Role")
    RolePermission = apps.get_model("users", "RolePermission")

    permissions_by_code = {}
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
        permissions_by_code[code] = permission

    role_permissions = []
    for role_code, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = Role.objects.filter(code=role_code).first()
        if role is None:
            continue
        role_permissions.extend(
            RolePermission(role=role, permission=permissions_by_code[permission_code])
            for permission_code in permission_codes
            if permission_code in permissions_by_code
        )

    RolePermission.objects.bulk_create(role_permissions, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_seed_market_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_endpoint_access_permissions, migrations.RunPython.noop),
    ]
