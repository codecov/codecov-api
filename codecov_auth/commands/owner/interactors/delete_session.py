from django.contrib.sessions.models import Session as DjangoSession

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import Session


class DeleteSessionInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, sessionid: int) -> None:
        self.validate()

        try:
            session_to_delete = Session.objects.get(sessionid=sessionid)
            django_session_to_delete = DjangoSession.objects.get(
                session_key=session_to_delete.login_session_id
            )
            user_id_to_delete = int(
                django_session_to_delete.get_decoded().get("_auth_user_id", "0")
            )

            if user_id_to_delete == self.current_user.id:
                django_session_to_delete.delete()
        except (Session.DoesNotExist, DjangoSession.DoesNotExist):
            pass
