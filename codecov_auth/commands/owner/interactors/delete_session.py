from django.contrib.sessions.models import Session as DjangoSession

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import Session


class DeleteSessionInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, sessionid: str):
        self.validate()
        session_to_delete = Session.objects.get(sessionid=sessionid)
        DjangoSession.objects.filter(
            session_key=session_to_delete.login_session_id
        ).delete()
