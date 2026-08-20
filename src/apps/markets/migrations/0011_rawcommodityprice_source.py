# Generated manually to link raw commodity prices to managed integration sources.

from django.db import migrations, models
import django.db.models.deletion


def backfill_raw_price_sources(apps, schema_editor):
    RawCommodityPrice = apps.get_model("markets", "RawCommodityPrice")
    MarketIntegrationSource = apps.get_model("market_integrations", "MarketIntegrationSource")
    sources = {source.key: source for source in MarketIntegrationSource.objects.all()}
    for source_key, source in sources.items():
        RawCommodityPrice.objects.filter(source_key=source_key, source__isnull=True).update(source=source)


class Migration(migrations.Migration):

    dependencies = [
        ("market_integrations", "0003_marketintegrationsource"),
        ("markets", "0010_rename_market_officers_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="rawcommodityprice",
            name="source",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="raw_commodity_prices",
                to="market_integrations.marketintegrationsource",
            ),
        ),
        migrations.AddIndex(
            model_name="rawcommodityprice",
            index=models.Index(fields=["source", "price_date"], name="rcp_source_fk_date_idx"),
        ),
        migrations.RunPython(backfill_raw_price_sources, reverse_code=migrations.RunPython.noop),
    ]
