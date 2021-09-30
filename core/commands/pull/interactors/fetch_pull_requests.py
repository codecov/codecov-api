from asgiref.sync import sync_to_async
from codecov.commands.base import BaseInteractor

from core.models import Pull

class FetchPullRequestsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository):
        if not repository.pull_requests:
            return Pull.objects.none()
        return repository.pull_requests.all()