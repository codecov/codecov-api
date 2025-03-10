from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov_auth.models import Owner


class FetchOwnerInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, username):
        return Owner.objects.filter(username=username, service=self.service).first()
