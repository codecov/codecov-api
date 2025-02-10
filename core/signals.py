import logging
from typing import Any, Dict, List, Type, cast

from django.db.models.signals import post_save
from django.dispatch import receiver
from shared.django_apps.core.models import Commit

from core.models import Repository
from utils.shelter import ShelterPubsub

log = logging.getLogger(__name__)


@receiver(post_save, sender=Repository, dispatch_uid="shelter_sync_repo")
def update_repository(
    sender: Type[Repository], instance: Repository, **kwargs: Dict[str, Any]
) -> None:
    log.info(f"Signal triggered for repository {instance.repoid}")
    created: bool = cast(bool, kwargs["created"])
    changes: Dict[str, Any] = instance.tracker.changed()
    tracked_fields: List[str] = ["name", "upload_token", "author_id", "private"]

    if created or any(field in changes for field in tracked_fields):
        data = {
            "type": "repo",
            "sync": "one",
            "id": instance.repoid,
        }
        ShelterPubsub.get_instance().publish(data)


@receiver(post_save, sender=Commit, dispatch_uid="shelter_sync_commit")
def update_commit(
    sender: Type[Commit], instance: Commit, **kwargs: Dict[str, Any]
) -> None:
    branch: str = instance.branch
    if branch and ":" in branch:
        data = {
            "type": "commit",
            "sync": "one",
            "id": instance.id,
        }
        ShelterPubsub.get_instance().publish(data)
