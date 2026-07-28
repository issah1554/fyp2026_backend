from django.db import migrations, models


def seed_prediction_markets(apps, schema_editor):
    Market = apps.get_model("commodities", "Market")
    seeded_markets = [
        ("Ifakara Central Market", "IFAKARA001"),
        ("Morogoro Central Market", "MOROGOR001"),
    ]
    for name, public_id in seeded_markets:
        Market.objects.update_or_create(
            name=name,
            defaults={"is_active": True, "public_id": public_id},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("commodities", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Market",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(editable=False, max_length=10, unique=True)),
                ("name", models.CharField(max_length=150, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.RunPython(seed_prediction_markets, migrations.RunPython.noop),
    ]
