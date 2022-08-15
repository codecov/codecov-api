from datetime import datetime, timedelta

from asgiref.sync import sync_to_async
from django.conf import settings
from django.utils import timezone

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.models import Owner
from core.models import Commit, Repository
from services.task import TaskService
from timeseries.models import Dataset, MeasurementName


class ActivateFlagsMeasurementsInteractor(BaseInteractor):
    def validate(self, repo):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()
        if not repo:
            raise ValidationError("Repo not found")
        if not settings.TIMESERIES_ENABLED:
            raise ValidationError("Timeseries storage not enabled")

    def backfill(self, dataset: Dataset):
        oldest_commit = (
            Commit.objects.filter(repository_id=dataset.repository_id)
            .order_by("timestamp")
            .first()
        )

        newest_commit = (
            Commit.objects.filter(repository_id=dataset.repository_id)
            .order_by("-timestamp")
            .first()
        )

        if oldest_commit and newest_commit:
            # dates to span the entire range of commits
            start_date = oldest_commit.timestamp.date()
            start_date = datetime.fromordinal(start_date.toordinal())
            end_date = newest_commit.timestamp.date() + timedelta(days=1)
            end_date = datetime.fromordinal(end_date.toordinal())

            TaskService().backfill_dataset(
                dataset,
                start_date=start_date,
                end_date=end_date,
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
            self.backfill(dataset)

        return dataset
