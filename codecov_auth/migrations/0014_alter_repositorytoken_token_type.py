# Generated by Django 3.2.12 on 2022-08-04 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0013_alter_owner_organizations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="repositorytoken",
            name="token_type",
            field=models.CharField(
                choices=[("UPLOAD", "Upload"), ("PROFILING", "Profiling")],
                max_length=50,
            ),
        ),
    ]
