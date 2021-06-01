class BaseCommand:
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service

    def get_interactor_exec(self, InteractorKlass):
        interactor = InteractorKlass(self.current_user, self.service)
        return interactor.execute


class BaseInteractor:
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service
