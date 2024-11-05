from typing import Any

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from ..fetch_branches import FetchRepoBranchesInteractor


class FetchRepoBranchesInteractorTest(TransactionTestCase):
    def setUp(self) -> None:
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(
            author=self.org, name="gazebo", private=False, branch="main"
        )
        self.head = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(repository=self.repo)
        self.branches = [
            BranchFactory(repository=self.repo, head=self.head.commitid, name="test1"),
            BranchFactory(repository=self.repo, head=self.head.commitid, name="test2"),
        ]

    def execute(self, owner, repository, filters) -> FetchRepoBranchesInteractor:
        service = owner.service if owner else "github"
        return FetchRepoBranchesInteractor(owner, service).execute(repository, filters)

    def test_fetch_branches(self) -> None:
        repository = self.repo
        filters: dict[str, Any] = {}
        branches = async_to_sync(self.execute)(None, repository, filters)
        assert any(branch.name == "main" for branch in branches)
        assert any(branch.name == "test1" for branch in branches)
        assert any(branch.name == "test2" for branch in branches)
        assert len(branches) == 3

    def test_fetch_branches_unmerged(self) -> None:
        merged = CommitFactory(repository=self.repo, merged=True)
        BranchFactory(repository=self.repo, head=merged.commitid, name="merged")
        branches = [
            branch.name for branch in async_to_sync(self.execute)(None, self.repo, {})
        ]
        assert "merged" not in branches
        branches = [
            branch.name
            for branch in async_to_sync(self.execute)(
                None, self.repo, {"merged_branches": True}
            )
        ]
        assert "merged" in branches

    def test_fetch_branches_filtered_by_name(self) -> None:
        repository = self.repo
        filters = {"search_value": "tESt", "merged_branches": True}
        branches = async_to_sync(self.execute)(None, repository, filters)
        assert not any(branch.name == "main" for branch in branches)
        assert any(branch.name == "test1" for branch in branches)
        assert any(branch.name == "test2" for branch in branches)
        assert len(branches) == 2

    def test_fetch_branches_filtered_by_name_no_sql_injection(self) -> None:
        repository = self.repo
        malicious_filters = {
            "search_value": "'; DROP TABLE branches; --",
            "merged_branches": True,
        }
        find_branches_sql_injection_attempt = async_to_sync(self.execute)(
            None, repository, malicious_filters
        )
        assert (
            # assert no branches found with that branch name
            len(find_branches_sql_injection_attempt) == 0
        )

        # confirm data is unaltered after sql injection attempt
        find_branches = async_to_sync(self.execute)(None, repository, {})
        assert len(find_branches) == 3
