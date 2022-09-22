from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    version.objects.all().delete()
    v = version(version="v4.6.6")
    v.save()


class Migration(migrations.Migration):

    dependencies = [("core", "0015_commiterror.py")]

    operations = [migrations.RunPython(add_version)]
