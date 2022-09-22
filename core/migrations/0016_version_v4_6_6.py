from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    version.objects.all().delete()
    v = version(version="v4.6.6")
    v.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0009_version_v4_6_5")]

    operations = [migrations.RunPython(add_version)]
