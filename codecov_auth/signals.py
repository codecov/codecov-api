import logging
from datetime import datetime

from django.db.models.signals import post_save
from django.dispatch import receiver

from codecov_auth.models import Owner, OwnerProfile

log = logging.getLogger(__name__)


@receiver(post_save, sender=Owner)
def create_owner_profile_when_owner_is_created(
    sender, instance: Owner, created, **kwargs
):
    if created:
        return OwnerProfile.objects.create(
            owner_id=instance.ownerid,
            terms_agreement=False,
            terms_agreement_at=datetime.now(),
        )
