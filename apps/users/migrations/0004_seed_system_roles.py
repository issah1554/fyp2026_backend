from django.db import migrations

from apps.common.ids import generate_unique_public_id
from apps.users.system_permissions import DEFAULT_ROLE_PERMISSIONS, SYSTEM_ROLES


def seed_system_roles(apps, schema_editor):
    Role = apps.get_model("users", "Role")
    Permission = apps.get_model("users", "Permission")
    RolePermission = apps.get_model("users", "RolePermission")

    roles_by_code = {}
    for code, name, description, is_system in SYSTEM_ROLES:
        role = Role.objects.filter(code=code).first()
        if role is None:
            role = Role(
                public_id=generate_unique_public_id(Role),
                code=code,
                name=name,
                description=description,
                is_system=is_system,
            )
            role.save()
        else:
            role.name = name
            role.description = description
            role.is_system = is_system
            role.save(update_fields=["name", "description", "is_system"])
        roles_by_code[code] = role

    for role_code, permission_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = roles_by_code.get(role_code)
        if role is None:
            continue
        permissions = Permission.objects.filter(code__in=permission_codes)
        RolePermission.objects.bulk_create(
            [RolePermission(role=role, permission=permission) for permission in permissions],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_role_alter_rolepermission_role"),
    ]

    operations = [
        migrations.RunPython(seed_system_roles, migrations.RunPython.noop),
    ]
