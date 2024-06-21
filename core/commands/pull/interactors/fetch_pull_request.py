from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async


class FetchPullRequestInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, id):
        return repository.pull_requests.filter(pullid=id).first()
