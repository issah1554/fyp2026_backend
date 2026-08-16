from secrets import choice

from django.db import migrations, models


PUBLIC_ID_ALPHABET = "123456789BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz"
PUBLIC_ID_LENGTH = 10
MAX_CONSECUTIVE_LETTERS = 3


def generate_public_id():
    public_id = []
    consecutive_letters = 0
    previous_was_letter = False

    for _index in range(PUBLIC_ID_LENGTH):
        while True:
            character = choice(PUBLIC_ID_ALPHABET)
            is_letter = character.isalpha()
            next_run = (
                consecutive_letters + 1
                if is_letter and previous_was_letter
                else 1
                if is_letter
                else 0
            )

            if next_run <= MAX_CONSECUTIVE_LETTERS:
                break

        public_id.append(character)
        consecutive_letters = next_run
        previous_was_letter = is_letter

    return "".join(public_id)


def populate_profile_public_ids(apps, schema_editor):
    Profile = apps.get_model("api", "Profile")
    used_public_ids = set(Profile.objects.exclude(public_id="").values_list("public_id", flat=True))

    for profile in Profile.objects.filter(public_id=""):
        while True:
            public_id = generate_public_id()
            if public_id not in used_public_ids:
                used_public_ids.add(public_id)
                break

        profile.public_id = public_id
        profile.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_profile_email_verified_at_emailverificationtoken"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="public_id",
            field=models.CharField(blank=True, editable=False, max_length=10),
        ),
        migrations.RunPython(populate_profile_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="profile",
            name="public_id",
            field=models.CharField(editable=False, max_length=10, unique=True),
        ),
    ]
