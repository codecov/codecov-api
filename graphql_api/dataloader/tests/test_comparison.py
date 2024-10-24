from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from graphql_api.dataloader.comparison import ComparisonLoader


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


async def load_comparisons(repoid, keys):
    info = GraphQLResolveInfo()
    loader = ComparisonLoader.loader(info, repoid)
    return await loader.load_many(keys)


@patch("services.task.TaskService.compute_comparisons")
class ComparisonLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.repository = RepositoryFactory(name="test-repo-1")

    def _load(self, keys):
        return async_to_sync(load_comparisons)(self.repository.pk, keys)

    def test_compare_commits_new_comparison(self, compute_comparisons):
        commit1 = CommitFactory(repository=self.repository)
        commit2 = CommitFactory(repository=self.repository)

        comparison = CommitComparison.objects.filter(
            base_commit=commit1,
            compare_commit=commit2,
        ).first()
        assert comparison is None

        (comparison,) = self._load([(commit1.commitid, commit2.commitid)])
        assert comparison is not None
        assert comparison.base_commit == commit1
        assert comparison.compare_commit == commit2

        compute_comparisons.assert_called_once_with([comparison.pk])
        comparison.refresh_from_db()
        assert comparison.state == "pending"

    def test_compare_commits_existing_comparison(self, compute_comparisons):
        commit1 = CommitFactory(repository=self.repository)
        commit2 = CommitFactory(repository=self.repository)

        CommitComparisonFactory(
            base_commit=commit1,
            compare_commit=commit2,
            state="processed",
        )

        (comparison,) = self._load([(commit1.commitid, commit2.commitid)])
        assert comparison is not None
        assert comparison.base_commit == commit1
        assert comparison.compare_commit == commit2

        assert not compute_comparisons.called
        comparison.refresh_from_db()
        assert comparison.state == "processed"

    def test_compare_commits_multiple_comparisons(self, compute_comparisons):
        commit1 = CommitFactory(repository=self.repository)
        commit2 = CommitFactory(repository=self.repository)
        commit3 = CommitFactory(repository=self.repository)

        CommitComparisonFactory(
            base_commit=commit1,
            compare_commit=commit2,
        )

        comparison1, comparison2 = self._load(
            [
                (commit1.commitid, commit2.commitid),
                (commit2.commitid, commit3.commitid),
            ]
        )
        assert comparison1 is not None
        assert comparison1.base_commit == commit1
        assert comparison1.compare_commit == commit2
        assert comparison2 is not None
        assert comparison2.base_commit == commit2
        assert comparison2.compare_commit == commit3

        compute_comparisons.assert_called_once_with([comparison2.pk])
