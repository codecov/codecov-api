# Generated by Django 3.1.13 on 2022-04-27 10:53

from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False
    dependencies = [
        ("core", "0010_add_new_langs"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commitnotification",
            name="decoration_type",
            field=models.TextField(
                choices=[
                    ("standard", "Standard"),
                    ("upgrade", "Upgrade"),
                    ("upload_limit", "Upload Limit"),
                ],
                null=True,
            ),
        ),
        migrations.RunSQL(
            "ALTER TYPE decorations ADD VALUE IF NOT exists 'upload_limit';"
        ),
    ]
