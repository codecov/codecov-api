# Generated by Django 4.2.7 on 2024-01-17 17:00

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0045_repository_languages_last_updated"),
        ("reports", "0012_alter_repositoryflag_flag_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Test",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("external_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("testid", models.TextField(unique=True)),
                ("name", models.TextField()),
                ("testsuite", models.TextField()),
                ("env", models.TextField(default="")),
                (
                    "repository",
                    models.ForeignKey(
                        db_column="repoid",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tests",
                        to="core.repository",
                    ),
                ),
            ],
            options={
                "db_table": "reports_test",
            },
        ),
        migrations.CreateModel(
            name="TestInstance",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("external_id", models.UUIDField(default=uuid.uuid4, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("duration_seconds", models.FloatField()),
                ("outcome", models.IntegerField()),
                ("failure_message", models.TextField(null=True)),
                ("active", models.BooleanField()),
                ("timestamp", models.TextField()),
                (
                    "report",
                    models.ForeignKey(
                        db_column="upload_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="testinstances",
                        to="reports.reportsession",
                    ),
                ),
                (
                    "test",
                    models.ForeignKey(
                        db_column="test_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="testinstances",
                        to="reports.test",
                        to_field="testid",
                    ),
                ),
            ],
            options={
                "db_table": "reports_testinstance",
            },
        ),
        migrations.AddConstraint(
            model_name="test",
            constraint=models.UniqueConstraint(
                fields=("repository", "name", "testsuite", "env"),
                name="tests_repository_name_testsuite_env",
            ),
        ),
    ]
