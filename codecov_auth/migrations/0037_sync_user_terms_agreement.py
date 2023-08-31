# Generated by Django 4.2.2 on 2023-08-30 20:30

from django.db import migrations


def sync_agreements(apps, schema):
    owners = apps.get_model("codecov_auth", "Owner")
    for owner in owners.objects.all():
        if owner.user:
            user = owner.user
            user.terms_agreement = owner.profile.terms_agreement
            user.terms_agreement_at = owner.profile.terms_agreement_at
            user.save()

def reverse_func(apps, schema):
    # Only used for unit testing
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("codecov_auth", "0036_add_user_terms_agreement"),
    ]

    operations = [migrations.RunPython(sync_agreements, reverse_func)]
