from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from core.models import Repository


class FetchRepositoryInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner, name):
        return (
            Repository.objects.viewable_repos(self.current_user)
            .filter(author=owner, name=name)
            .with_cache_coverage()
            .select_related("author")
            .first()
        )
