from codecov.commands.base import BaseCommand

from .interactors.delete_flag import DeleteFlagInteractor


class FlagCommands(BaseCommand):
    def delete_flag(self, *args, **kwargs):
        return self.get_interactor(DeleteFlagInteractor).execute(*args, **kwargs)
