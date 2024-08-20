import pytest
from django.contrib.auth.models import AnonymousUser

from codecov.commands.exceptions import MissingService
from core.commands.commit import CommitCommands
from core.tests.factories import OwnerFactory

from ..base import BaseCommand, BaseInteractor


def test_base_command():
    command = BaseCommand(None, "github")
    # test command is properly init
    assert command.current_owner is None
    assert command.service == "github"
    # test get_interactor
    interactor = command.get_interactor(BaseInteractor)
    assert interactor.current_owner is None
    assert interactor.current_user == AnonymousUser()
    assert interactor.service == "github"
    # test get_command
    command_command = command.get_command("commit")
    assert isinstance(command_command, CommitCommands)


def test_base_interactor_with_missing_required_service():
    with pytest.raises(MissingService) as excinfo:
        BaseInteractor(None, None)

    assert excinfo.value.message == "Missing required service"

@pytest.mark.django_db
def test_base_interactor_missing_user_in_owner():
    owner = OwnerFactory()
    owner.user = None
    command = BaseCommand(owner, "github", None)

    interactor = command.get_interactor(BaseInteractor)
    assert interactor.current_user == AnonymousUser()


@pytest.mark.django_db
def test_base_interactor_with_owner():
    owner = OwnerFactory()
    command = BaseCommand(owner, "github")
    interactor = command.get_interactor(BaseInteractor)

    assert interactor.current_owner == owner
    assert interactor.current_user == owner.user
    assert interactor.service == "github"
    assert interactor.requires_service is True
