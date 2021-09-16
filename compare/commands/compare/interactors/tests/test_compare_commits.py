from datetime import datetime

from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from core.tests.factories import CommitFactory
from compare.tests.factories import CommitComparisonFactory

from ..compare_commits import CompareCommitsInteractor


class CompareCommitsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = AnonymousUser()
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.comparison = CommitComparisonFactory()

    @patch(
        "compare.commands.compare.interactors.compare_commits.TaskService.compute_comparison"
    )
    @async_to_sync
    async def test_when_comparison_doesnt_exist(self, task_compute_comparison):
        compare = await CompareCommitsInteractor(AnonymousUser(), "github").execute(
            self.commit, self.parent_commit
        )
        assert compare.base_commit is self.parent_commit
        assert compare.compare_commit is self.commit
        task_compute_comparison.assert_called_with(compare.id)

    @patch(
        "compare.commands.compare.interactors.compare_commits.TaskService.compute_comparison"
    )
    @async_to_sync
    async def test_when_comparison_exists(self, task_compute_comparison):
        compare = await CompareCommitsInteractor(AnonymousUser(), "github").execute(
            self.comparison.compare_commit, self.comparison.base_commit
        )
        assert compare.id == self.comparison.id
        task_compute_comparison.assert_not_called()

    @patch(
        "compare.commands.compare.interactors.compare_commits.TaskService.compute_comparison"
    )
    @async_to_sync
    async def test_when_stale_comparison_exists(self, task_compute_comparison):
        self.comparison.compare_commit.updatestamp = datetime.now()
        compare = await CompareCommitsInteractor(AnonymousUser(), "github").execute(
            self.comparison.compare_commit, self.comparison.base_commit
        )
        assert compare.id == self.comparison.id
        task_compute_comparison.assert_called_with(compare.id)
