from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0006_profile_role_fk"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE email_verification_tokens
            DROP CONSTRAINT IF EXISTS api_emailverificationtoken_user_id_7e807130_fk_auth_user_id;

            ALTER TABLE email_verification_tokens
            ADD CONSTRAINT api_emailverificationtoken_user_id_7e807130_fk_auth_user_id
            FOREIGN KEY (user_id)
            REFERENCES auth_user (id)
            ON DELETE CASCADE
            DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql="""
            ALTER TABLE email_verification_tokens
            DROP CONSTRAINT IF EXISTS api_emailverificationtoken_user_id_7e807130_fk_auth_user_id;

            ALTER TABLE email_verification_tokens
            ADD CONSTRAINT api_emailverificationtoken_user_id_7e807130_fk_auth_user_id
            FOREIGN KEY (user_id)
            REFERENCES auth_user (id)
            DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
    ]
