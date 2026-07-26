from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="UssdSubscriber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(editable=False, max_length=10, unique=True)),
                ("phone_number", models.CharField(max_length=32, unique=True)),
                ("full_name", models.CharField(max_length=150)),
                (
                    "role",
                    models.CharField(
                        choices=[("farmer", "Farmer"), ("entrepreneur", "Entrepreneur"), ("buyer", "Buyer")],
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["full_name"]},
        ),
        migrations.CreateModel(
            name="UssdPriceAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "commodity",
                    models.CharField(choices=[("maize", "Maize"), ("rice", "Rice")], max_length=32),
                ),
                ("target_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "subscriber",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="price_alerts",
                        to="ussd.ussdsubscriber",
                    ),
                ),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.AddConstraint(
            model_name="ussdpricealert",
            constraint=models.UniqueConstraint(
                fields=("subscriber", "commodity"),
                name="unique_ussd_price_alert_per_commodity",
            ),
        ),
    ]
