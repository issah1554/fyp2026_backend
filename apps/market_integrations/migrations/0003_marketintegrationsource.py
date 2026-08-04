# Generated manually for DB-backed market integration sources.

import uuid

from django.db import migrations, models


def seed_sources(apps, schema_editor):
    MarketIntegrationSource = apps.get_model("market_integrations", "MarketIntegrationSource")
    sources = [
        {
            "key": "platform_a",
            "name": "Platform A",
            "source_type": "api",
            "base_url": "http://localhost:3001",
            "prices_path": "/api/prices",
            "health_path": "/api/health",
        },
        {
            "key": "platform_b",
            "name": "Platform B",
            "source_type": "api",
            "base_url": "http://localhost:3002",
            "prices_path": "/api/prices",
            "health_path": "/api/health",
        },
        {
            "key": "internal",
            "name": "Internal System",
            "source_type": "internal",
            "base_url": "",
            "prices_path": "",
            "health_path": "",
        },
        {
            "key": "viwanda",
            "name": "Ministry of Industry and Trade",
            "source_type": "scraper",
            "base_url": "https://www.viwanda.go.tz",
            "prices_path": "/documents/product-prices-domestic",
            "health_path": "/documents/product-prices-domestic",
        },
    ]
    for source in sources:
        source.setdefault("public_id", uuid.uuid4().hex[:10].upper())
        MarketIntegrationSource.objects.update_or_create(
            key=source["key"],
            defaults=source,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("market_integrations", "0002_remove_integratedmarketprice_imp_source_commodity_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketIntegrationSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.CharField(editable=False, max_length=10, unique=True)),
                ("key", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("source_type", models.CharField(choices=[("internal", "Internal"), ("api", "API"), ("scraper", "Scraper"), ("file", "File")], default="api", max_length=20)),
                ("base_url", models.URLField(blank=True, max_length=500)),
                ("prices_path", models.CharField(blank=True, default="/api/prices", max_length=255)),
                ("health_path", models.CharField(blank=True, default="/api/health", max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("last_imported_at", models.DateTimeField(blank=True, null=True)),
                ("last_seen_record_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "market_integration_sources",
                "ordering": ["name"],
                "indexes": [
                    models.Index(fields=["key"], name="mis_key_idx"),
                    models.Index(fields=["is_active", "deleted_at"], name="mis_active_idx"),
                ],
            },
        ),
        migrations.RunPython(seed_sources, reverse_code=migrations.RunPython.noop),
    ]
