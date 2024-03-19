from loguru import logger

from django.core.management.base import BaseCommand, CommandError, CommandParser
from redis import Redis
from shared.config import get_config

from core.models import Commit
from services.task import TaskService


def get_storage_redis():
    return Redis.from_url(get_config("services", "redis_url"))


def get_celery_redis():
    return Redis.from_url(get_config("services", "celery_broker"))


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--batch-size", type=int)
        parser.add_argument("--queue-name", type=str, default="archive")

    def handle(self, *args, **options):
        batch_size = options.get("batch_size", 1000)

        storage_redis = get_storage_redis()
        celery_redis = get_celery_redis()

        queue_name = options.get("queue_name")
        queue_length = celery_redis.llen(queue_name)

        if queue_length > 0:
            logger.warning(
                "Backfill commits queue not drained",
                extra=dict(
                    queue_length=queue_length,
                ),
            )
            return

        commits = Commit.objects.all().only("id")

        # this stores the oldest commit id that has already been backfilled
        commit_id = storage_redis.get("backfill_commits_id")
        if commit_id:
            commit_id = int(commit_id)
            commits = commits.filter(id__lt=commit_id)

        commits = commits.order_by("-id")[:batch_size]
        for commit in commits:
            TaskService().backfill_commit_data(commit_id=commit.id)
            if commit_id is None or commit.id < commit_id:
                commit_id = commit.id

        if len(commits) == 0:
            logger.warning(
                "Backfill commits finished", extra=dict(backfill_commits_id=commit_id)
            )
        else:
            # store the oldest commit id that has already been backfilled
            storage_redis.set("backfill_commits_id", commit_id)
