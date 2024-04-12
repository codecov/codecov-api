from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Session
from django.contrib.sessions.models import Session as DjangoSession
from django.core.handlers.wsgi import WSGIRequest


class DeleteSessionInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, sessionid: str, request: WSGIRequest):
        self.validate()

        current_logged_in_session = request.session.session_key
        session_to_delete = Session.objects.get(sessionid=sessionid)

        if session_to_delete.login_session_id == current_logged_in_session:
            raise ValidationError("Cannot delete session currently being used")

        DjangoSession.objects.filter(session_key=session_to_delete.login_session_id).delete()