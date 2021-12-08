from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    version.objects.all().delete()
    v = version(version="v4.6.2")
    v.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_auto_20210916_0313"),
    ]

    operations = [
        migrations.RunPython(add_version),
    ]
