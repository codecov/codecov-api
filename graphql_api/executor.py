from .commands.owner import OwnerCommands


mapping = {"owner": OwnerCommands}


class Executor:
    def __init__(self, request):
        self.request = request
        self.user = request.user
        self.service = request.resolver_match.kwargs["service"]

    def get_command(self, namespace):
        KlassCommand = mapping[namespace]
        return KlassCommand(self.user, self.service)
