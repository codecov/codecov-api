# Generated by Django 4.2.2 on 2023-08-28 17:42

from django.db import migrations, models
from shared.django_apps.migration_utils import RiskyAlterField


class Migration(migrations.Migration):
    dependencies = [
        ("codecov_auth", "0038_alter_owner_uses_invoice"),
    ]

    operations = [
        RiskyAlterField(
            model_name="owner",
            name="uses_invoice",
            field=models.BooleanField(default=False, null=False),
        ),
    ]
