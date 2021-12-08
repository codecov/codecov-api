from django.db import migrations


def add_version(apps, schema):
    version = apps.get_model("core", "Version")
    versions = version.objects.all()
    count = versions.count()
    if count == 1:
        v = versions[0]
        v.version = "v4.6.3"
        v.save()
        pass
    elif count == 0:
        v = version(version="v4.6.3")
        v.save()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_version_v4_6_2"),
    ]

    operations = [
        migrations.RunPython(add_version),
    ]
