# Generated by Django 4.2.7 on 2023-12-06 13:28

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    BEGIN;
    --
    -- Add field report_type to commitreport
    --
    ALTER TABLE "reports_commitreport" ADD COLUMN "report_type" varchar(100) NULL;
    COMMIT;
    """

    dependencies = [
        ("reports", "0010_alter_reportdetails_files_array_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="commitreport",
            name="report_type",
            field=models.CharField(
                choices=[
                    ("coverage", "Coverage"),
                    ("test_results", "Test Results"),
                    ("bundle_analysis", "Bundle Analysis"),
                ],
                max_length=100,
                null=True,
            ),
        ),
    ]
