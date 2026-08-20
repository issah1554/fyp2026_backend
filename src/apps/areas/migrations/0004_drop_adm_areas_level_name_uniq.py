from django.db import migrations


def drop_old_level_name_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE adm_areas DROP CONSTRAINT IF EXISTS adm_areas_level_name_uniq"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("areas", "0003_admarea_adm_areas_parent_level_name_uniq"),
    ]

    operations = [
        migrations.RunPython(drop_old_level_name_constraint, migrations.RunPython.noop),
    ]
