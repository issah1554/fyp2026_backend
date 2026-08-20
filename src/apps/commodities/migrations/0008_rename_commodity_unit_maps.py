from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("commodities", "0007_alter_commodityunitmap_id"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="commodityunitmap",
            table="commodity_allowed_units",
        ),
    ]
