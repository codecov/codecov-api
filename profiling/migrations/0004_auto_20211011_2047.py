# Generated by Django 3.1.13 on 2021-10-11 20:47

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("profiling", "0003_profilingcommit_commit_sha")]

    operations = [
        migrations.AddField(
            model_name="profilingcommit",
            name="environment",
            field=models.CharField(max_length=100, null=True),
        )
    ]
