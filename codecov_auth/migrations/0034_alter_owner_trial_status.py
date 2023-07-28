# Generated by Django 4.1.7 on 2023-07-27 00:38

from django.db import migrations, models

from utils.migrations import RiskyRunSQL


class Migration(migrations.Migration):
    """
        BEGIN;
    --
    -- Alter field trial_status on owner
    --
    -- (no-op)
    COMMIT;
    """

    dependencies = [
        ("codecov_auth", "0033_sentryuser"),
    ]

    operations = [
        migrations.AlterField(
            model_name="owner",
            name="trial_status",
            field=models.CharField(
                choices=[
                    ("not_started", "Not Started"),
                    ("ongoing", "Ongoing"),
                    ("expired", "Expired"),
                    ("cannot_trial", "Cannot Trial"),
                ],
                default="not_started",
                max_length=50,
                null=True,
            ),
        ),
        RiskyRunSQL(
            "alter table owners alter column trial_status set default 'not_started';"
        ),
    ]
