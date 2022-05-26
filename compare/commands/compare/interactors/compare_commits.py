import pytz
from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from compare.models import CommitComparison
from services.task import TaskService


class CompareCommitsInteractor(BaseInteractor):
    def get_or_create_comparison(self, head_commit, compare_to_commit):
        commit_comparison, created = CommitComparison.objects.get_or_create(
            base_commit=compare_to_commit, compare_commit=head_commit
        )

        # optimization: set these on the result for `needs_calculation` below
        commit_comparison.base_commit = compare_to_commit
        commit_comparison.compare_commit = head_commit

        return (commit_comparison, created)

    def trigger_task(self, comparison):
        TaskService().compute_comparison(comparison.id)

    @sync_to_async
    def execute(self, head_commit, compare_to_commit):
        if not head_commit or not compare_to_commit:
            return None
        comparison, created = self.get_or_create_comparison(
            head_commit, compare_to_commit
        )
        if created or self.needs_recalculation(comparison):
            comparison.state = CommitComparison.CommitComparisonStates.PENDING
            comparison.save()
            self.trigger_task(comparison)
        return comparison

    def needs_recalculation(self, comparison):
        timezone = pytz.utc
        return (
            comparison.compare_commit.updatestamp
            and timezone.normalize(comparison.updated_at)
            < timezone.localize(comparison.compare_commit.updatestamp)
        ) or (
            comparison.base_commit.updatestamp
            and timezone.normalize(comparison.updated_at)
            < timezone.localize(comparison.base_commit.updatestamp)
        )
