from django.conf import settings

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from timeseries.helpers import trigger_backfill
from timeseries.models import Dataset, MeasurementName


class ActivateMeasurementsInteractor(BaseInteractor):
    @sync_to_async
    def execute(
        self, repo_name: str, owner_name: str, measurement_type: MeasurementName
    ) -> Dataset:
        if not settings.TIMESERIES_ENABLED:
            raise ValidationError("Timeseries storage not enabled")

        _owner, repo = self.resolve_owner_and_repo(
            owner_name, repo_name, only_viewable=True, only_active=True
        )

        dataset, created = Dataset.objects.get_or_create(
            name=measurement_type.value,
            repository_id=repo.pk,
        )

        if created:
            trigger_backfill(dataset)

        return dataset
