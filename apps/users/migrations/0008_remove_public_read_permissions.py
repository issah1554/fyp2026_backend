from django.db import migrations


PUBLIC_READ_PERMISSION_CODES = [
    "commodities.categories.list",
    "commodities.categories.read",
    "commodities.units.list",
    "commodities.units.read",
    "commodities.list",
    "commodities.read",
    "markets.list",
    "markets.read",
    "market_prices.list",
    "market_prices.read",
    "market_prices.latest",
    "commodity_prices.list",
    "commodity_prices.history",
    "commodity_prices.compare",
    "areas.list",
    "areas.read",
    "listings.list",
    "listings.read",
]


def remove_public_read_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "Permission")
    Permission.objects.filter(code__in=PUBLIC_READ_PERMISSION_CODES).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0007_seed_endpoint_access_permissions"),
    ]

    operations = [
        migrations.RunPython(remove_public_read_permissions, migrations.RunPython.noop),
    ]
