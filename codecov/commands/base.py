from django.contrib.auth.models import AnonymousUser

from codecov.commands.exceptions import MissingService
from codecov_auth.models import Owner, User


class BaseCommand:
    def __init__(
        self, current_owner: Owner, service: str, current_user: User = AnonymousUser()
    ):
        self.current_user = current_user
        self.current_owner = current_owner
        self.service = service
        self.executor = None

    def get_interactor(self, InteractorKlass):
        return InteractorKlass(
            current_owner=self.current_owner,
            service=self.service,
            current_user=self.current_user,
        )

    def get_command(self, namespace):
        """
        Allow a command to call another command
        """
        if not self.executor:
            # local import to avoid circular import; I'm not too happy about
            # this pattern yet
            from .executor import get_executor_from_command

            self.executor = get_executor_from_command(self)
        return self.executor.get_command(namespace)


class BaseInteractor:
    requires_service = True

    def __init__(
        self, current_owner: Owner, service: str, current_user: User = AnonymousUser()
    ):
        self.current_user = current_user
        self.current_owner = current_owner
        self.service = service

        if not self.service and self.requires_service:
            raise MissingService()

        if self.current_owner and not self.current_user.is_authenticated:
            self.current_user = self.current_owner
