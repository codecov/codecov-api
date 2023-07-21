from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from core.models import Repository


class FetchRepositoryInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner, name):
        return (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=owner, name=name)
            .with_recent_coverage()
            .with_oldest_commit_at()
            .select_related("author")
            .first()
        )
