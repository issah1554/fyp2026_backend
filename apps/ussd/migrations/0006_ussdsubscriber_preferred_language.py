from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ussd", "0005_ussdmarketrecommendation_window_end_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ussdsubscriber",
            name="preferred_language",
            field=models.CharField(
                choices=[("en", "English"), ("sw", "Swahili")],
                default="en",
                max_length=8,
            ),
        ),
    ]
