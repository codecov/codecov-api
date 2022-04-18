from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    version.objects.all().delete()
    v = version(version="v4.6.4")
    v.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0007_version_v4_6_3")]

    operations = [migrations.RunPython(add_version)]
