import json

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from google.cloud import pubsub_v1

from core.models import Repository

_pubsub_publisher = None


def _get_pubsub_publisher():
    global _pubsub_publisher
    if not _pubsub_publisher:
        _pubsub_publisher = pubsub_v1.PublisherClient()
    return _pubsub_publisher


@receiver(post_save, sender=Repository, dispatch_uid="shelter_sync_repo")
def update_repository(sender, instance, **kwargs):
    pubsub_project_id = settings.SHELTER_PUBSUB_PROJECT_ID
    topic_id = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
    if pubsub_project_id and topic_id:
        publisher = _get_pubsub_publisher()
        topic_path = publisher.topic_path(pubsub_project_id, topic_id)
        publisher.publish(
            topic_path, json.dumps({"sync": instance.repoid}).encode("utf-8")
        )
