from asgiref.sync import sync_to_async

from core.models import Commit
from codecov.commands.base import BaseInteractor


class FetchCommitInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, commit_id):
        return repository.commits.filter(commitid=commit_id).first()
