from typing import Optional

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q
from shared.config import get_config
from shared.torngit.gitlab import Gitlab

from codecov_auth.models import Owner
from core.models import Repository
from services.repo_providers import RepoProviderService
from utils.repos import get_bot_user


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        # this can be used to retry if there's an error - restart the command
        # from the last ID printed before failure
        parser.add_argument("--starting-repoid", type=int)

    def handle(self, *args, **options):
        repos = Repository.objects.filter(
            Q(author__service="gitlab") & ~Q(hookid=None),
        ).order_by("repoid")

        if options["starting_repoid"]:
            repos = repos.filter(pk__gte=options["starting_repoid"])

        webhook_url = get_config("setup", "webhook_url") or get_config(
            "setup", "codecov_url"
        )
        webhook_secret = get_config("gitlab", "webhook_secret")

        for repo in repos:

            user = get_bot_user(repo)
            if user is None:
                print("no bot user")
                continue

            gitlab: Gitlab = RepoProviderService().get_adapter(user, repo)
            async_to_sync(gitlab.edit_webhook)(
                hookid=repo.hookid,
                name=None,
                url=f"{webhook_url}/webhooks/gitlab",
                events={
                    "push_events": True,
                    "issues_events": False,
                    "merge_requests_events": True,
                    "tag_push_events": False,
                    "note_events": False,
                    "job_events": False,
                    "build_events": True,
                    "pipeline_events": True,
                    "wiki_events": False,
                },
                secret=webhook_secret,
            )
