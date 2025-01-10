from typing import Any, Dict, Optional, Type, cast

from django.db.models.signals import post_save
from django.dispatch import receiver

from codecov_auth.models import OrganizationLevelToken, Owner, OwnerProfile
from utils.shelter import ShelterPubsub


@receiver(post_save, sender=Owner)
def create_owner_profile_when_owner_is_created(
    sender: Type[Owner], instance: Owner, created: bool, **kwargs: Dict[str, Any]
) -> Optional[OwnerProfile]:
    if created:
        return OwnerProfile.objects.create(owner_id=instance.ownerid)


@receiver(
    post_save, sender=OrganizationLevelToken, dispatch_uid="shelter_sync_org_token"
)
def update_org_token(
    sender: Type[OrganizationLevelToken],
    instance: OrganizationLevelToken,
    **kwargs: Dict[str, Any],
) -> None:
    data = {
        "type": "org_token",
        "sync": "one",
        "id": instance.id,
    }
    ShelterPubsub.get_instance().publish(data)


@receiver(post_save, sender=Owner, dispatch_uid="shelter_sync_owner")
def update_owner(
    sender: Type[Owner], instance: Owner, **kwargs: Dict[str, Any]
) -> None:
    """
    Shelter tracks a limited set of Owner fields - only update if those fields have changed.
    """
    created: bool = cast(bool, kwargs["created"])
    tracked_fields = [
        "upload_token_required_for_public_repos",
        "username",
        "service",
    ]
    if created or any(instance.tracker.has_changed(field) for field in tracked_fields):
        data = {
            "type": "owner",
            "sync": "one",
            "id": instance.ownerid,
        }
        ShelterPubsub.get_instance().publish(data)
