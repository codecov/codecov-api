from .constants import WEBHOOK_EVENTS
from utils.config import get_config

import asyncio

def delete_webhook_on_provider(repository_service, repo):
    """
        Deletes webhook on provider
    """
    return asyncio.run(repository_service.delete_webhook(hookid=repo.hookid))


def create_webhook_on_provider(repository_service, repo):
    """
        Creates webhook on provider
    """

    webhook_url = (
        get_config('setup', 'webhook_url') or get_config('setup', 'codecov_url')
    )

    return asyncio.run(
        repository_service.post_webhook(
            f'Codecov Webhook. {webhook_url}',
            f'{webhook_url}/webhooks/{repository_service.service}',
            WEBHOOK_EVENTS[repository_service.service],
            get_config(repository_service.service, 'webhook_secret', default='testixik8qdauiab1yiffydimvi72ekq')
        )
    ).get('id')
