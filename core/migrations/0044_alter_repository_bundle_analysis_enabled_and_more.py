# Generated by Django 4.2.7 on 2024-01-10 12:28

import django.contrib.postgres.fields
from django.db import migrations, models
from shared.django_apps.migration_utils import RiskyAlterField


class Migration(migrations.Migration):
    """
    BEGIN;
    --
    -- Alter field bundle_analysis_enabled on repository
    --
    ALTER TABLE "repos" ALTER COLUMN "bundle_analysis_enabled" DROP NOT NULL;
    --
    -- Alter field languages on repository
    --
    ALTER TABLE "repos" ALTER COLUMN "languages" DROP NOT NULL;
    COMMIT;
    """

    dependencies = [
        ("core", "0043_repository_bundle_analysis_enabled"),
    ]

    operations = [
       RiskyAlterField(
            model_name="repository",
            name="bundle_analysis_enabled",
            field=models.BooleanField(default=False, null=True),
        ),
        RiskyAlterField(
            model_name="repository",
            name="languages",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(),
                blank=True,
                default=[],
                null=True,
                size=None,
            ),
        ),
    ]
