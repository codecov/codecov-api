# Generated by Django 4.2.2 on 2023-09-05 16:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0037_sync_user_terms_agreement"),
    ]

    operations = [
        migrations.RunSQL(
            sql=migrations.RunSQL.noop,
            state_operations=[
                migrations.RemoveField(
                    model_name="ownerprofile",
                    name="terms_agreement",
                ),
                migrations.RemoveField(
                    model_name="ownerprofile",
                    name="terms_agreement_at",
                ),
            ]
        )
    ]
