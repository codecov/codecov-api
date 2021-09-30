from codecov.commands.base import BaseCommand

from .interactors.fetch_pull_requests import FetchPullRequestsInteractor


class PullCommands(BaseCommand):
    def fetch_pull_requests(self, repository):
        return self.get_interactor(FetchPullRequestsInteractor).execute(repository)