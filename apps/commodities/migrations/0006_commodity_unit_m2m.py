"""
Migration 0006: Commodity ↔ CommodityUnit many-to-many refactor

Changes:
  1. Create CommodityUnitMap through-table
  2. Add Commodity.units M2M field (through CommodityUnitMap)
  3. DATA MIGRATION: copy existing unit_ref rows → CommodityUnitMap (is_primary=True)
  4. Remove Commodity.unit (CharField)
  5. Remove Commodity.unit_ref (ForeignKey)
  6. Remove Commodity.description
  7. Remove CommodityUnit.description
  8. Remove the orphaned commodities_market table (ghost Market from old models.py)
  9. Remove the orphaned commodities_marketpricerecord table (MarketPriceRecord
     from old models.py — had no db_table set so Django named it automatically)
"""

from django.db import migrations, models
import django.db.models.deletion


def migrate_unit_ref_to_m2m(apps, schema_editor):
    """Copy Commodity.unit_ref FK data into the new CommodityUnitMap through-table."""
    Commodity = apps.get_model("commodities", "Commodity")
    CommodityUnitMap = apps.get_model("commodities", "CommodityUnitMap")

    to_create = []
    for commodity in Commodity.objects.filter(unit_ref_id__isnull=False).iterator():
        to_create.append(
            CommodityUnitMap(
                commodity_id=commodity.pk,
                unit_id=commodity.unit_ref_id,
                is_primary=True,
            )
        )

    if to_create:
        CommodityUnitMap.objects.bulk_create(to_create, ignore_conflicts=True)


def reverse_migrate_unit_ref(apps, schema_editor):
    """Restore unit_ref from the primary CommodityUnitMap entry (best-effort)."""
    Commodity = apps.get_model("commodities", "Commodity")
    CommodityUnitMap = apps.get_model("commodities", "CommodityUnitMap")

    for mapping in CommodityUnitMap.objects.filter(is_primary=True).select_related("commodity").iterator():
        Commodity.objects.filter(pk=mapping.commodity_id).update(unit_ref_id=mapping.unit_id)


class Migration(migrations.Migration):

    dependencies = [
        ("commodities", "0005_merge_20260728_0001"),
    ]

    operations = [
        # ── 1. Create through-table ──────────────────────────────────────────
        migrations.CreateModel(
            name="CommodityUnitMap",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "commodity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unit_maps",
                        to="commodities.commodity",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commodity_maps",
                        to="commodities.commodityunit",
                    ),
                ),
                (
                    "is_primary",
                    models.BooleanField(
                        default=False,
                        help_text="Marks this as the default display unit for the commodity.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "commodity_unit_maps",
                "ordering": ["-is_primary", "unit__name"],
            },
        ),
        migrations.AddConstraint(
            model_name="commodityunitmap",
            constraint=models.UniqueConstraint(
                fields=["commodity", "unit"],
                name="unique_commodity_unit_map",
            ),
        ),

        # ── 2. Add M2M field on Commodity ────────────────────────────────────
        migrations.AddField(
            model_name="commodity",
            name="units",
            field=models.ManyToManyField(
                blank=True,
                related_name="commodities",
                through="commodities.CommodityUnitMap",
                to="commodities.commodityunit",
            ),
        ),

        # ── 3. Data migration: unit_ref → CommodityUnitMap ───────────────────
        migrations.RunPython(
            migrate_unit_ref_to_m2m,
            reverse_code=reverse_migrate_unit_ref,
        ),

        # ── 4. Drop Commodity.unit (free-text CharField) ─────────────────────
        migrations.RemoveField(
            model_name="commodity",
            name="unit",
        ),

        # ── 5. Drop Commodity.unit_ref (ForeignKey) ───────────────────────────
        migrations.RemoveField(
            model_name="commodity",
            name="unit_ref",
        ),

        # ── 6. Drop Commodity.description ────────────────────────────────────
        migrations.RemoveField(
            model_name="commodity",
            name="description",
        ),

        # ── 7. Drop CommodityUnit.description ────────────────────────────────
        migrations.RemoveField(
            model_name="commodityunit",
            name="description",
        ),

        # ── 8. Drop orphaned ghost Market table (commodities_market) ─────────
        migrations.DeleteModel(
            name="Market",
        ),

        # ── 9. Drop orphaned MarketPriceRecord table ──────────────────────────
        migrations.DeleteModel(
            name="MarketPriceRecord",
        ),
    ]
