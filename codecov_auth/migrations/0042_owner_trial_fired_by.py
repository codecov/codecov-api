# Generated by Django 4.2.3 on 2023-09-19 09:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0041_auto_20230918_1825"),
    ]

    operations = [
        migrations.AddField(
            model_name="owner",
            name="trial_fired_by",
            field=models.IntegerField(null=True),
        ),
    ]
