from asgiref.sync import sync_to_async

from core.models import Branch
from codecov.commands.base import BaseInteractor


class FetchBranchInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, commit_id):
        return ()
