from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("markets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="marketcommodityprice",
            name="max_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="marketcommodityprice",
            name="min_price",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]
