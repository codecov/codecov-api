from codecov.commands.base import BaseCommand

from .interactors.fetch_impacted_files import FetchImpactedFiles


class CompareCommands(BaseCommand):
    def fetch_impacted_files(self, comparsion, filters):
        return self.get_interactor(FetchImpactedFiles).execute(comparsion, filters)
