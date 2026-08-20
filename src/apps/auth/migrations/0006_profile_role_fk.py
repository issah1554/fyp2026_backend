import django.db.models.deletion
from uuid import uuid4
from django.db import migrations, models

import apps.auth.models


SYSTEM_ROLE_NAMES = {
    "admin": "Administrator",
    "farmer": "Farmer",
    "entrepreneur": "Entrepreneur",
    "buyer": "Buyer",
    "market_officer": "Market Officer",
    "researcher": "Researcher",
}


def migrate_profile_roles(apps, schema_editor):
    Profile = apps.get_model("api", "Profile")
    Role = apps.get_model("users", "Role")

    roles_by_code = {role.code: role for role in Role.objects.all()}
    for code, name in SYSTEM_ROLE_NAMES.items():
        if code not in roles_by_code:
            public_id = uuid4().hex[:10]
            while Role.objects.filter(public_id=public_id).exists():
                public_id = uuid4().hex[:10]
            role = Role.objects.create(
                public_id=public_id,
                code=code,
                name=name,
                description="",
                is_system=True,
            )
            roles_by_code[code] = role

    default_role = roles_by_code["farmer"]
    for profile in Profile.objects.all():
        role = roles_by_code.get(profile.role, default_role)
        profile.role_ref_id = role.pk
        profile.save(update_fields=["role_ref"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_seed_system_roles"),
        ("api", "0005_passwordresettoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="role_ref",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profiles",
                to="users.role",
            ),
        ),
        migrations.RunPython(migrate_profile_roles, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="profile",
            name="role",
        ),
        migrations.RenameField(
            model_name="profile",
            old_name="role_ref",
            new_name="role",
        ),
        migrations.AlterField(
            model_name="profile",
            name="role",
            field=models.ForeignKey(
                default=apps.auth.models.get_default_role_id,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="profiles",
                to="users.role",
            ),
        ),
    ]
