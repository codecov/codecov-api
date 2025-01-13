import json
import logging
from typing import Any, Dict

from django.conf import settings
from google.cloud import pubsub_v1

log = logging.getLogger(__name__)


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
        if not settings.SHELTER_ENABLED:
            return

        if not self.pubsub_publisher:
            self.pubsub_publisher = pubsub_v1.PublisherClient()
        pubsub_project_id: str = settings.SHELTER_PUBSUB_PROJECT_ID

        # topic_id has REPO in the name but it is used for all types of objects
        topic_id: str = settings.SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID
        self.topic_path = self.pubsub_publisher.topic_path(pubsub_project_id, topic_id)

    def publish(self, data: Dict[str, Any]) -> None:
        if not settings.SHELTER_ENABLED:
            return

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
