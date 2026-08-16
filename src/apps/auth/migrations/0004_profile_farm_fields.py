from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_profile_public_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="farm_group",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="profile",
            name="farm_location",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
