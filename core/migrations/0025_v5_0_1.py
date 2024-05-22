from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    version.objects.all().delete()
    v = version(version="v5.0.1")
    v.save()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_alter_commit_timestamp_alter_commit_updatestamp_and_more")
    ]

    operations = [migrations.RunPython(add_version)]
