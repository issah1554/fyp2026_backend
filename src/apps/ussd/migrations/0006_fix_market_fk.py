"""
Migration 0006: Fix UssdMarketPrediction and UssdMarketRecommendation market FK
to point to markets.Market instead of the now-deleted commodities.Market ghost.
"""

from django.db import migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("commodities", "0006_commodity_unit_m2m"),
        ("markets", "0001_initial"),
        ("ussd", "0005_ussdmarketrecommendation_window_end_and_more"),
    ]

    operations = [
        # Re-point UssdMarketPrediction.market → markets.Market
        migrations.AlterField(
            model_name="ussdmarketprediction",
            name="market",
            field=django.db.models.fields.related.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ussd_predictions",
                to="markets.market",
            ),
        ),
        # Re-point UssdMarketRecommendation.market → markets.Market
        migrations.AlterField(
            model_name="ussdmarketrecommendation",
            name="market",
            field=django.db.models.fields.related.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ussd_recommendations",
                to="markets.market",
            ),
        ),
    ]
