from django.db import migrations


def seed_prediction_commodities(apps, schema_editor):
    Commodity = apps.get_model("commodities", "Commodity")
    seeded_commodities = [
        ("Beans", "kg", "BEANS00001"),
        ("Rice", "kg", "RICE000001"),
    ]
    for name, unit, public_id in seeded_commodities:
        commodity = Commodity.objects.filter(name=name).order_by("id").first()
        if commodity is None:
            Commodity.objects.create(
                name=name,
                unit=unit,
                description=f"Seeded prediction commodity for {name}.",
                public_id=public_id,
            )
            continue

        updates = []
        if not commodity.public_id:
            commodity.public_id = public_id
            updates.append("public_id")
        if not commodity.unit:
            commodity.unit = unit
            updates.append("unit")
        if not commodity.description:
            commodity.description = f"Seeded prediction commodity for {name}."
            updates.append("description")
        if updates:
            commodity.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ("commodities", "0002_market"),
    ]

    operations = [
        migrations.RunPython(seed_prediction_commodities, migrations.RunPython.noop),
    ]
