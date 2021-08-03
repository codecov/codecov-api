class BaseCommand:
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service
        self.executor = None

    def get_interactor(self, InteractorKlass):
        return InteractorKlass(self.current_user, self.service)

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
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service
