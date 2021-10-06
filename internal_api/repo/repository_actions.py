import asyncio
import logging

from asgiref.sync import async_to_sync
from django.conf import settings

from utils.config import get_config
from webhook_handlers.constants import (
    BitbucketWebhookEvents,
    GitHubWebhookEvents,
    GitLabWebhookEvents,
)

log = logging.getLogger(__name__)


WEBHOOK_EVENTS = {
    "github": GitHubWebhookEvents.repository_events,
    "github_enterprise": [
        "pull_request",
        "delete",
        "push",
        "public",
        "status",
        "repository",
    ],
    "bitbucket": BitbucketWebhookEvents.subscribed_events,
    # https://confluence.atlassian.com/bitbucketserver/post-service-webhook-for-bitbucket-server-776640367.html
    "bitbucket_server": [],
    "gitlab": GitLabWebhookEvents.subscribed_events,
    "gitlab_enterprise": GitLabWebhookEvents.subscribed_events,
}


@async_to_sync
async def delete_webhook_on_provider(repository_service, repo):
    """
        Deletes webhook on provider
    """
    return await repository_service.delete_webhook(hookid=repo.hookid)


def create_webhook_on_provider(repository_service, repo):
    """
        Creates webhook on provider
    """

    webhook_url = settings.WEBHOOK_URL

    log.info(
        "Resetting webhook with webhook url: %s"
        % f"{webhook_url}/webhooks/{repository_service.service}"
    )

    return async_to_sync(repository_service.post_webhook)(
        f"Codecov Webhook. {webhook_url}",
        f"{webhook_url}/webhooks/{repository_service.service}",
        WEBHOOK_EVENTS[repository_service.service],
        get_config(
            repository_service.service,
            "webhook_secret",
            default="testixik8qdauiab1yiffydimvi72ekq",
        ),
    ).get("id")
