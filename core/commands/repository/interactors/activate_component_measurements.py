from django.conf import settings

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.models import Repository
from timeseries.helpers import trigger_backfill
from timeseries.models import Dataset, MeasurementName


class ActivateComponentMeasurementsInteractor(BaseInteractor):
    def validate(self, repo):
        if not repo:
            raise ValidationError("Repo not found")
        if not settings.TIMESERIES_ENABLED:
            raise ValidationError("Timeseries storage not enabled")

    @sync_to_async
    def execute(self, repo_name, owner_name):
        author = Owner.objects.filter(username=owner_name, service=self.service).first()
        repo = (
            Repository.objects.viewable_repos(self.current_user)
            .filter(author=author, name=repo_name, active=True)
            .first()
        )
        self.validate(repo)

        dataset, created = Dataset.objects.get_or_create(
            name=MeasurementName.COMPONENT_COVERAGE.value,
            repository_id=repo.pk,
        )

        if created:
            trigger_backfill(dataset)

        return dataset
