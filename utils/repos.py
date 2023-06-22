from typing import Optional

from codecov_auth.models import Owner
from core.models import Repository


def get_bot_user(repo: Repository) -> Optional[Owner]:
    if repo.bot and repo.bot.oauth_token:
        return repo.bot
    if repo.author.bot and repo.author.bot.oauth_token:
        return repo.author.bot
    if repo.author.oauth_token:
        return repo.author
