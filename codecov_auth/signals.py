import logging
from datetime import datetime

from django.db.models.signals import post_save
from django.dispatch import receiver

from codecov_auth.models import Owner, OwnerProfile


@receiver(post_save, sender=Owner)
def create_owner_profile_when_owner_is_created(
    sender, instance: Owner, created, **kwargs
):
    if created:
        return OwnerProfile.objects.create(
            owner_id=instance.ownerid,
        )
