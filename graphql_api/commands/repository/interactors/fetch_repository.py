from asgiref.sync import sync_to_async

from core.models import Repository
from graphql_api.commands.base import BaseInteractor


class FetchRepositoryInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner, name):
        return (
            Repository.objects.viewable_repos(self.current_user)
            .filter(author=owner, name=name)
            .select_related("author")
            .first()
        )
