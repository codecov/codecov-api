# Generated by Django 4.2.3 on 2023-10-30 16:16

from django.db import migrations, models

from utils.migrations import RiskyAddIndex


class Migration(migrations.Migration):
    """
    BEGIN;
    --
    -- Create index pulls_repoid_id on field(s) repository, id of model pull
    --
    CREATE INDEX "pulls_repoid_id" ON "pulls" ("repoid", "id");
    COMMIT;
    """

    dependencies = [
        ("core", "0037_alter_commitnotification_decoration_type"),
    ]

    operations = [
        RiskyAddIndex(
            model_name="pull",
            index=models.Index(fields=["repository", "id"], name="pulls_repoid_id"),
        ),
    ]
