from django.db import migrations


def remove_researcher_role_and_user(apps, schema_editor):
    Role = apps.get_model("users", "Role")
    User = apps.get_model("auth", "User")
    
    # Delete researcher_sample user if exists
    User.objects.filter(username="researcher_sample").delete()
    
    # Delete researcher role if exists
    Role.objects.filter(code="researcher").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_seed_system_roles"),
    ]

    operations = [
        migrations.RunPython(remove_researcher_role_and_user, migrations.RunPython.noop),
    ]
