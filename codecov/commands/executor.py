from utils.services import get_long_service_name

from codecov_auth.commands.owner import OwnerCommands
from core.commands.repository import RepositoryCommands
from core.commands.commit import CommitCommands
from core.commands.branch import BranchCommands


mapping = {
    "commit": CommitCommands,
    "owner": OwnerCommands,
    "repository": RepositoryCommands,
    "branch": BranchCommands,
}


class Executor:
    def __init__(self, user, service):
        self.user = user
        self.service = service

    def get_command(self, namespace):
        KlassCommand = mapping[namespace]
        return KlassCommand(self.user, self.service)


def get_executor_from_request(request):
    service_in_url = request.resolver_match.kwargs["service"]
    return Executor(user=request.user, service=get_long_service_name(service_in_url))


def get_executor_from_command(command):
    return Executor(user=command.user, service=command.service)
