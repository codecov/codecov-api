# Generated by Django 3.1.13 on 2022-05-11 17:32

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0011_add_decoration_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='repository',
            name='bot',
            field=models.ForeignKey(blank=True, db_column='bot', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bot_repos', to=settings.AUTH_USER_MODEL),
        ),
    ]
