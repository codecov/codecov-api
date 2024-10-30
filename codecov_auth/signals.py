import json
import logging
from typing import Any, Dict, Optional, Type

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from google.cloud import pubsub_v1

from codecov_auth.models import OrganizationLevelToken, Owner, OwnerProfile

log = logging.getLogger(__name__)


@receiver(post_save, sender=Owner)
def create_owner_profile_when_owner_is_created(
    sender: Type[Owner], instance: Owner, created: bool, **kwargs: Dict[str, Any]
) -> Optional[OwnerProfile]:
    if created:
        return OwnerProfile.objects.create(owner_id=instance.ownerid)


class ShelterPubsub:
    pubsub_publisher = None
    _instance = None

    @classmethod
    def get_instance(cls) -> "ShelterPubsub":
        """
        This class needs the Django settings to be fully loaded before it can be instantiated,
        therefore use this method to get an instance rather than instantiating directly.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        if not self.pubsub_publisher:
            self.pubsub_publisher = pubsub_v1.PublisherClient()
        pubsub_project_id: str = settings.SHELTER_PUBSUB_PROJECT_ID

        # topic_id has REPO in the name but it is used for all types of objects
        topic_id: str = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
        self.topic_path = self.pubsub_publisher.topic_path(pubsub_project_id, topic_id)

    def publish(self, data: Dict[str, Any]) -> None:
        try:
            self.pubsub_publisher.publish(
                self.topic_path,
                json.dumps(data).encode("utf-8"),
            )
        except Exception as e:
            log.warning(
                "Failed to publish a message",
                extra=dict(data_to_publish=data, error=e),
            )


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
    created: bool = kwargs["created"]
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
