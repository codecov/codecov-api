from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory

from ..fetch_branches import FetchRepoBranchesInteractor


class FetchRepoBranchesInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(
            author=self.org, name="gazebo", private=False, branch="master"
        )
        self.head = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(repository=self.repo)
        self.branches = [
            BranchFactory(repository=self.repo, head=self.head.commitid, name="test1"),
            BranchFactory(repository=self.repo, head=self.head.commitid, name="test2"),
        ]

    def execute(self, owner, repository, filters):
        service = owner.service if owner else "github"
        return FetchRepoBranchesInteractor(owner, service).execute(repository, filters)

    def test_fetch_branches(self):
        repository = self.repo
        filters = {}
        branches = async_to_sync(self.execute)(None, repository, filters)
        assert any(branch.name == "master" for branch in branches)
        assert any(branch.name == "test1" for branch in branches)
        assert any(branch.name == "test2" for branch in branches)
        assert len(branches) == 3

    def test_fetch_branches_unmerged(self):
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
