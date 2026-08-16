from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0009_remove_profile_role_profile_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="avatar_url",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
