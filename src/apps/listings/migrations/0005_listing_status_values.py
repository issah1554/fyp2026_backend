from django.db import migrations, models


def forward_statuses(apps, schema_editor):
    CommodityListing = apps.get_model("listings", "CommodityListing")
    CommodityListing.objects.filter(status="active").update(status="available")
    CommodityListing.objects.filter(status="sold").update(status="sold_out")
    CommodityListing.objects.filter(status="inactive").update(status="draft")


def reverse_statuses(apps, schema_editor):
    CommodityListing = apps.get_model("listings", "CommodityListing")
    CommodityListing.objects.filter(status="available").update(status="active")
    CommodityListing.objects.filter(status="sold_out").update(status="sold")
    CommodityListing.objects.filter(status="draft").update(status="inactive")


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0004_move_admarea_to_areas_app"),
    ]

    operations = [
        migrations.RunPython(forward_statuses, reverse_statuses),
        migrations.AlterField(
            model_name="commoditylisting",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("sold_out", "Sold Out"),
                    ("draft", "Draft"),
                    ("archived", "Archived"),
                ],
                default="available",
                max_length=50,
            ),
        ),
    ]
