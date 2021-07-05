class BaseCommand:
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service

    def get_interactor(self, InteractorKlass):
        return InteractorKlass(self.current_user, self.service)


class BaseInteractor:
    def __init__(self, current_user, service):
        self.current_user = current_user
        self.service = service
