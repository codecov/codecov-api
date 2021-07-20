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
    def __init__(self, request):
        self.request = request
        self.user = request.user
        service_in_url = request.resolver_match.kwargs["service"]
        self.service = get_long_service_name(service_in_url)

    def get_command(self, namespace):
        KlassCommand = mapping[namespace]
        return KlassCommand(self.user, self.service)
