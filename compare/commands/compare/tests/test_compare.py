import asyncio
from django.test import TransactionTestCase
from core.tests.factories import CommitFactory

from codecov_auth.tests.factories import OwnerFactory
from ..compare import CompareCommands


class CompareCommandsTest(TransactionTestCase):
    def setUp(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.user = OwnerFactory(username="codecov-user")
        self.command = CompareCommands(self.user, "github")

        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )

    async def test_compare_commit_when_no_parents(self):
        compare = await self.command.compare_commit_with_parent(self.parent_commit)
        assert compare is None

    async def test_compare_commit_when_parents(self):
        compare = await self.command.compare_commit_with_parent(self.commit)
        assert compare is not None
