# Generated by Django 4.2.7 on 2024-01-09 22:39

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0041_pull_bundle_analysis_commentid"),
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
                ("name", models.TextField()),
                ("testsuite", models.TextField()),
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
                    ),
                ),
            ],
            options={
                "db_table": "reports_testinstance",
            },
        ),
    ]
