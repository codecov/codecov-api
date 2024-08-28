# Generated by Django 3.1.13 on 2021-09-24 10:03

import uuid

import django.contrib.postgres.fields
import django.db.models.deletion
from django.conf import settings  # noqa: F401
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("codecov_auth", "0002_auto_20210817_1346")]

    operations = [
        migrations.AddField(
            model_name="owner", name="business_email", field=models.TextField(null=True)
        ),
        migrations.AddField(
            model_name="owner",
            name="onboarding_completed",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="OwnerProfile",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("external_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "type_projects",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.TextField(
                            choices=[
                                ("PERSONAL", "Personal"),
                                ("YOUR_ORG", "Your Org"),
                                ("OPEN_SOURCE", "Open Source"),
                                ("EDUCATIONAL", "Educational"),
                            ]
                        ),
                        default=list,
                        size=None,
                    ),
                ),
                (
                    "goals",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.TextField(
                            choices=[
                                ("STARTING_WITH_TESTS", "Starting With Tests"),
                                ("IMPROVE_COVERAGE", "Improve Coverage"),
                                ("MAINTAIN_COVERAGE", "Maintain Coverage"),
                                ("OTHER", "Other"),
                            ]
                        ),
                        default=list,
                        size=None,
                    ),
                ),
                ("other_goal", models.TextField(null=True)),
                (
                    "owner",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="codecov_auth.owner",
                    ),
                ),
            ],
            options={"abstract": False},
        ),
    ]
