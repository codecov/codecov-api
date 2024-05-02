from codecov.commands.base import BaseCommand

from .interactors.delete_component_measurements import (
    DeleteComponentMeasurementsInteractor,
)


class ComponentCommands(BaseCommand):
    def delete_component_measurements(self, *args, **kwargs):
        return self.get_interactor(DeleteComponentMeasurementsInteractor).execute(
            *args, **kwargs
        )
