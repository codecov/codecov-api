class BaseCommand:
    def __init__(self, current_user):
        self.current_user = current_user


class BaseInteractor:
    def __init__(self, current_user):
        self.current_user = current_user
