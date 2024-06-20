import pytest
from django.contrib.auth.models import AnonymousUser

from codecov.commands.exceptions import MissingService
from core.commands.commit import CommitCommands

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
