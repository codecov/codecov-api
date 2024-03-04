# Generated by Django 4.2.7 on 2024-02-23 19:27

import django.db.models.deletion
import psqlextra.backend.migrations.operations.add_default_partition
import psqlextra.backend.migrations.operations.create_partitioned_model
import psqlextra.manager.manager
import psqlextra.models.partitioned
import psqlextra.types
from django.db import migrations, models


class Migration(migrations.Migration):

    """
    BEGIN;
    --
    -- Create partitioned model UserMeasurement
    --
    CREATE TABLE "user_measurements" ("id" bigint NOT NULL GENERATED BY DEFAULT AS IDENTITY, "created_at" timestamp with time zone NOT NULL, "uploader_used" varchar NOT NULL, "private_repo" boolean NOT NULL, "report_type" varchar(100) NULL, "commit_id" bigint NOT NULL, "owner_id" integer NOT NULL, "repo_id" integer NOT NULL, "upload_id" bigint NOT NULL, PRIMARY KEY ("id", "created_at")) PARTITION BY RANGE ("created_at");
    --
    -- Creates default partition 'default' on UserMeasurement
    --
    CREATE TABLE "user_measurements_default" PARTITION OF "user_measurements" DEFAULT;
    ALTER TABLE "user_measurements" ADD CONSTRAINT "user_measurements_commit_id_cebc077d_fk_commits_id" FOREIGN KEY ("commit_id") REFERENCES "commits" ("id") DEFERRABLE INITIALLY DEFERRED;
    ALTER TABLE "user_measurements" ADD CONSTRAINT "user_measurements_owner_id_ef39e26d_fk_owners_ownerid" FOREIGN KEY ("owner_id") REFERENCES "owners" ("ownerid") DEFERRABLE INITIALLY DEFERRED;
    ALTER TABLE "user_measurements" ADD CONSTRAINT "user_measurements_repo_id_88a7cde6_fk_repos_repoid" FOREIGN KEY ("repo_id") REFERENCES "repos" ("repoid") DEFERRABLE INITIALLY DEFERRED;
    ALTER TABLE "user_measurements" ADD CONSTRAINT "user_measurements_upload_id_e18ce658_fk_reports_upload_id" FOREIGN KEY ("upload_id") REFERENCES "reports_upload" ("id") DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX "user_measurements_commit_id_cebc077d" ON "user_measurements" ("commit_id");
    CREATE INDEX "user_measurements_owner_id_ef39e26d" ON "user_measurements" ("owner_id");
    CREATE INDEX "user_measurements_repo_id_88a7cde6" ON "user_measurements" ("repo_id");
    CREATE INDEX "user_measurements_upload_id_e18ce658" ON "user_measurements" ("upload_id");
    CREATE INDEX "i_owner" ON "user_measurements" ("owner_id");
    CREATE INDEX "owner_repo" ON "user_measurements" ("owner_id", "repo_id");
    CREATE INDEX "owner_private_repo" ON "user_measurements" ("owner_id", "private_repo");
    CREATE INDEX "owner_private_repo_report_type" ON "user_measurements" ("owner_id", "private_repo", "report_type");
    COMMIT;
    """

    initial = True

    dependencies = [
        ("reports", "0014_rename_env_test_flags_hash_and_more"),
        ("codecov_auth", "0051_user_customer_intent"),
        ("core", "0047_increment_version"),
    ]

    operations = [
        psqlextra.backend.migrations.operations.create_partitioned_model.PostgresCreatePartitionedModel(
            name="UserMeasurement",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("uploader_used", models.CharField()),
                ("private_repo", models.BooleanField()),
                (
                    "report_type",
                    models.CharField(
                        choices=[
                            ("coverage", "Coverage"),
                            ("test_results", "Test Results"),
                            ("bundle_analysis", "Bundle Analysis"),
                        ],
                        max_length=100,
                        null=True,
                    ),
                ),
                (
                    "commit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_measurements",
                        to="core.commit",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_measurements",
                        to="codecov_auth.owner",
                    ),
                ),
                (
                    "repo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_measurements",
                        to="core.repository",
                    ),
                ),
                (
                    "upload",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="user_measurements",
                        to="reports.reportsession",
                    ),
                ),
            ],
            options={
                "db_table": "user_measurements",
                "indexes": [
                    models.Index(fields=["owner"], name="i_owner"),
                    models.Index(fields=["owner", "repo"], name="owner_repo"),
                    models.Index(
                        fields=["owner", "private_repo"], name="owner_private_repo"
                    ),
                    models.Index(
                        fields=["owner", "private_repo", "report_type"],
                        name="owner_private_repo_report_type",
                    ),
                ],
            },
            partitioning_options={
                "method": psqlextra.types.PostgresPartitioningMethod["RANGE"],
                "key": ["created_at"],
            },
            bases=(psqlextra.models.partitioned.PostgresPartitionedModel,),
            managers=[
                ("objects", psqlextra.manager.manager.PostgresManager()),
            ],
        ),
        psqlextra.backend.migrations.operations.add_default_partition.PostgresAddDefaultPartition(
            model_name="UserMeasurement",
            name="default",
        ),
    ]
