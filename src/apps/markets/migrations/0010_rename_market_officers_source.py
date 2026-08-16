from django.db import migrations


def rename_market_officers_source(apps, schema_editor):
    MarketCommodityPrice = apps.get_model("markets", "MarketCommodityPrice")
    RawCommodityPrice = apps.get_model("markets", "RawCommodityPrice")

    MarketCommodityPrice._base_manager.filter(source_key="market_officers").update(
        source_key="internal",
        source_name="Internal System",
    )
    RawCommodityPrice._base_manager.filter(source_key="market_officers").update(
        source_key="internal",
        source_name="Internal System",
    )


def restore_market_officers_source(apps, schema_editor):
    MarketCommodityPrice = apps.get_model("markets", "MarketCommodityPrice")
    RawCommodityPrice = apps.get_model("markets", "RawCommodityPrice")

    MarketCommodityPrice._base_manager.filter(source_key="internal", source_name="Internal System").update(
        source_key="market_officers",
        source_name="Market Officers",
    )
    RawCommodityPrice._base_manager.filter(source_key="internal", source_name="Internal System").update(
        source_key="market_officers",
        source_name="Market Officers",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("markets", "0009_rawcommodityprice"),
    ]

    operations = [
        migrations.RunPython(rename_market_officers_source, reverse_code=restore_market_officers_source),
    ]
