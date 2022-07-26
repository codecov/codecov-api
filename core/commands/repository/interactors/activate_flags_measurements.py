from asgiref.sync import sync_to_async
from django.utils import timezone

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Owner
from core.models import Repository
from services.task import TaskService
from timeseries.models import Dataset, MeasurementName


class ActivateFlagsMeasurementsInteractor(BaseInteractor):
    def validate(self, repo):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not repo:
            raise ValidationError("Repo not found")

    def backfill(self, repository):
        TaskService().backfill_repo(
            repository,
            # this date is a bit arbitrary - just picking something old enough such
            # that it encompasses most (if not all) commit timestamps in the database
            start_date=timezone.datetime(2000, 1, 1),
            end_date=timezone.now(),
        )

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
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=repo.pk,
        )

        if created:
            self.backfill(repo)

        return dataset
