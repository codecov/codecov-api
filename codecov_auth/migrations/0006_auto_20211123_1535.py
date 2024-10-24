# Generated by Django 3.1.13 on 2021-11-23 15:35

import django.db.models.deletion
from django.conf import settings  # noqa: F401
from django.db import migrations, models

import codecov_auth.models


class Migration(migrations.Migration):
    dependencies = [("codecov_auth", "0005_auto_20211029_1709")]

    operations = [
        migrations.AlterField(
            model_name="owner",
            name="plan",
            field=models.TextField(default="users-basic", null=True),
        ),
        migrations.AlterField(
            model_name="ownerprofile",
            name="owner",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="profile",
                to="codecov_auth.owner",
            ),
        ),
        migrations.AlterField(
            model_name="repositorytoken",
            name="key",
            field=models.CharField(
                default=codecov_auth.models._generate_key,
                editable=False,
                max_length=40,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="repositorytoken",
            name="valid_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
