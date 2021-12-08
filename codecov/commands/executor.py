from codecov_auth.commands.owner import OwnerCommands
from compare.commands.compare import CompareCommands
from core.commands.branch import BranchCommands
from core.commands.commit import CommitCommands
from core.commands.pull import PullCommands
from core.commands.repository import RepositoryCommands
from core.commands.upload import UploadCommands
from utils.services import get_long_service_name

mapping = {
    "commit": CommitCommands,
    "owner": OwnerCommands,
    "repository": RepositoryCommands,
    "branch": BranchCommands,
    "compare": CompareCommands,
    "pull": PullCommands,
    "upload": UploadCommands,
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
    return Executor(user=command.current_user, service=command.service)
