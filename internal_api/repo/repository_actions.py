from django.conf import settings

from utils.config import get_config
from webhook_handlers.constants import GitHubWebhookEvents

import asyncio


WEBHOOK_EVENTS = {
    "github": GitHubWebhookEvents.repository_events,
    "github_enterprise": [
        "pull_request",
        "delete",
        "push",
        "public",
        "status",
        "repository"
    ],
    "bitbucket": [
        "repo:push", "pullrequest:created", "pullrequest:updated",
        "pullrequest:fulfilled", "repo:commit_status_created",
        "repo:commit_status_updated"
    ],
    # https://confluence.atlassian.com/bitbucketserver/post-service-webhook-for-bitbucket-server-776640367.html
    "bitbucket_server": [],
    "gitlab": {
        "push_events": True,
        "issues_events": False,
        "merge_requests_events": True,
        "tag_push_events": False,
        "note_events": False,
        "job_events": False,
        "build_events": True,
        "pipeline_events": True,
        "wiki_events": False
    },
    "gitlab_enterprise": {
        "push_events": True,
        "issues_events": False,
        "merge_requests_events": True,
        "tag_push_events": False,
        "note_events": False,
        "job_events": False,
        "build_events": True,
        "pipeline_events": True,
        "wiki_events": False
    }
}


def delete_webhook_on_provider(repository_service, repo):
    """
        Deletes webhook on provider
    """
    return asyncio.run(repository_service.delete_webhook(hookid=repo.hookid))


def create_webhook_on_provider(repository_service, repo):
    """
        Creates webhook on provider
    """

    webhook_url = settings.WEBHOOK_URL

    return asyncio.run(
        repository_service.post_webhook(
            f'Codecov Webhook. {webhook_url}',
            f'{webhook_url}/webhooks/{repository_service.service}',
            WEBHOOK_EVENTS[repository_service.service],
            get_config(repository_service.service, 'webhook_secret', default='testixik8qdauiab1yiffydimvi72ekq')
        )
    ).get('id')
