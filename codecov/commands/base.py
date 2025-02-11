from django.conf import settings
from django.contrib.auth.models import AnonymousUser

import services.self_hosted as self_hosted
from codecov.commands.exceptions import (
    MissingService,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner, User
from core.models import Repository


class BaseCommand:
    def __init__(self, current_owner: Owner, service: str, current_user: User = None):
        self.current_user = current_user or AnonymousUser()
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

    def __init__(self, current_owner: Owner, service: str, current_user: User = None):
        self.current_user = current_user or AnonymousUser()
        self.current_owner = current_owner
        self.service = service

        if not self.service and self.requires_service:
            raise MissingService()

        if self.current_owner:
            self.current_user = self.current_owner.user

    def ensure_is_admin(self, owner: Owner) -> None:
        """
        Ensures that the `current_owner` is an admin of `owner`,
        or raise `Unauthorized` otherwise.
        """

        if not current_user_part_of_org(self.current_owner, owner):
            raise Unauthorized()

        if settings.IS_ENTERPRISE:
            if not self_hosted.is_admin_owner(self.current_owner):
                raise Unauthorized()
        else:
            if not owner.is_admin(self.current_owner):
                raise Unauthorized()

    def resolve_owner_and_repo(
        self,
        owner_username: str,
        repo_name: str,
        ensure_is_admin: bool = False,
        only_viewable: bool = False,
        only_active: bool = False,
    ) -> tuple[Owner, Repository]:
        """
        Resolves the `Owner` and `Repository` based on the passed `owner_username`
        and `repo_name` respectively.

        If `ensure_is_admin` is set, this will also ensure that the `current_owner` is an
        admin on the resolved `Owner`.
        """
        if ensure_is_admin and not self.current_user.is_authenticated:
            raise Unauthenticated()

        owner = Owner.objects.filter(
            service=self.service, username=owner_username
        ).first()

        if not owner:
            raise ValidationError("Owner not found")

        if ensure_is_admin:
            self.ensure_is_admin(owner)

        repo_query = Repository.objects
        if only_viewable:
            repo_query = repo_query.viewable_repos(self.current_owner)
        if only_active:
            repo_query = repo_query.filter(active=True)

        repo = repo_query.filter(author=owner, name=repo_name).first()
        if not repo:
            raise ValidationError("Repo not found")

        return (owner, repo)
