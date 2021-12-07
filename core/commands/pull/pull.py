from codecov.commands.base import BaseCommand

from .interactors.fetch_pull_request import FetchPullRequestInteractor
from .interactors.fetch_pull_requests import FetchPullRequestsInteractor


class PullCommands(BaseCommand):
    def fetch_pull_request(self, repository, id):
        return self.get_interactor(FetchPullRequestInteractor).execute(repository, id)

    def fetch_pull_requests(self, repository, filters):
        return self.get_interactor(FetchPullRequestsInteractor).execute(
            repository, filters
        )
