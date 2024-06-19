import json

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from google.cloud import pubsub_v1

from core.models import Repository
from shared.django_apps.core.models import Commit

_pubsub_publisher = None


def _get_pubsub_publisher():
    global _pubsub_publisher
    if not _pubsub_publisher:
        _pubsub_publisher = pubsub_v1.PublisherClient()
    return _pubsub_publisher


@receiver(post_save, sender=Repository, dispatch_uid="shelter_sync_repo")
def update_repository(sender, instance: Repository, **kwargs):
    created = kwargs["created"]
    changes = instance.tracker.changed()
    if created or any([field in changes for field in ["name", "upload_token"]]):
        pubsub_project_id = settings.SHELTER_PUBSUB_PROJECT_ID
        topic_id = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
        if pubsub_project_id and topic_id:
            publisher = _get_pubsub_publisher()
            topic_path = publisher.topic_path(pubsub_project_id, topic_id)
            publisher.publish(
                topic_path,
                json.dumps(
                    {
                        "type": "repo",
                        "sync": "one",
                        "id": instance.repoid,
                    }
                ).encode("utf-8"),
            )

@receiver(post_save, sender=Commit, dispatch_uid="shelter_sync_commit")
def update_commit(sender, instance: Commit, **kwargs):
    branch = instance.branch
    if branch and ":" in branch:
        pubsub_project_id = settings.SHELTER_PUBSUB_PROJECT_ID
        topic_id = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
        if pubsub_project_id and topic_id:
            publisher = _get_pubsub_publisher()
            topic_path = publisher.topic_path(pubsub_project_id, topic_id)
            publisher.publish(
                topic_path,
                json.dumps(
                    {
                        "type": "commit",
                        "sync": "one",
                        "id": instance.id,
                    }
                ).encode("utf-8"),
            )
