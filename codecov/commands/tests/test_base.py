from django.contrib.auth.models import AnonymousUser

from core.commands.commit import CommitCommands

from ..base import BaseCommand, BaseInteractor


def test_base_command():
    command = BaseCommand(AnonymousUser(), "github")
    # test command is properly init
    assert command.current_user == AnonymousUser()
    assert command.service == "github"
    # test get_interactor
    interactor = command.get_interactor(BaseInteractor)
    assert interactor.current_user == AnonymousUser()
    assert interactor.service == "github"
    # test get_command
    command_command = command.get_command("commit")
    assert isinstance(command_command, CommitCommands)
