# Generated by Django 3.2.12 on 2022-07-18 13:11

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("timeseries", "0005_uniqueness_constraints"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dataset",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.TextField()),
                ("repository_id", models.IntegerField()),
                ("backfilled", models.BooleanField(default=False)),
            ],
        ),
        migrations.AddIndex(
            model_name="dataset",
            index=models.Index(
                fields=["name", "repository_id"], name="timeseries__name_f96a15_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="dataset",
            constraint=models.UniqueConstraint(
                fields=("name", "repository_id"), name="name_repository_id_unique"
            ),
        ),
    ]
