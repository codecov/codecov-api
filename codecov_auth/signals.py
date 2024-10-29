import json
import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from google.cloud import pubsub_v1

from codecov_auth.models import OrganizationLevelToken, Owner, OwnerProfile

log = logging.getLogger(__name__)


@receiver(post_save, sender=Owner)
def create_owner_profile_when_owner_is_created(
    sender, instance: Owner, created, **kwargs
):
    if created:
        return OwnerProfile.objects.create(owner_id=instance.ownerid)


_pubsub_publisher = None


def _get_pubsub_publisher():
    global _pubsub_publisher
    if not _pubsub_publisher:
        _pubsub_publisher = pubsub_v1.PublisherClient()
    return _pubsub_publisher


@receiver(
    post_save, sender=OrganizationLevelToken, dispatch_uid="shelter_sync_org_token"
)
def update_org_token(sender, instance: OrganizationLevelToken, **kwargs):
    pubsub_project_id = settings.SHELTER_PUBSUB_PROJECT_ID
    topic_id = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
    if pubsub_project_id and topic_id:
        publisher = _get_pubsub_publisher()
        topic_path = publisher.topic_path(pubsub_project_id, topic_id)
        publisher.publish(
            topic_path,
            json.dumps(
                {
                    "type": "org_token",
                    "sync": "one",
                    "id": instance.id,
                }
            ).encode("utf-8"),
        )


@receiver(post_save, sender=Owner, dispatch_uid="shelter_sync_owner")
def update_owner(sender, instance: Owner, **kwargs):
    """
    Shelter tracks a limited set of Owner fields - only update if those fields have changed.
    """
    created = kwargs["created"]
    tracked_fields = [
        "upload_token_required_for_public_repos",
        "username",
        "service",
    ]
    if created or any(instance.tracker.has_changed(field) for field in tracked_fields):
        pubsub_project_id = settings.SHELTER_PUBSUB_PROJECT_ID
        topic_id = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
        if pubsub_project_id and topic_id:
            try:
                publisher = _get_pubsub_publisher()
                topic_path = publisher.topic_path(pubsub_project_id, topic_id)
                publisher.publish(
                    topic_path,
                    json.dumps(
                        {
                            "type": "owner",
                            "sync": "one",
                            "id": instance.ownerid,
                        }
                    ).encode("utf-8"),
                )
            except Exception as e:
                log.warning(
                    "Failed to publish message for owner",
                    extra=dict(owner_id=instance.pk, error=e),
                )
