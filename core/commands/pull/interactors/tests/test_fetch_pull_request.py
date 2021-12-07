import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from core.tests.factories import OwnerFactory, PullFactory, RepositoryFactory
from internal_api import pull
from reports.tests.factories import UploadFactory

from ..fetch_pull_request import FetchPullRequestInteractor


class FetchPullRequestInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.pr = PullFactory(repository_id=self.repo.repoid)

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchPullRequestInteractor(current_user, service).execute(*args)

    async def test_fetch_when_pull_request_doesnt_exist(self):
        pr = await self.execute(None, self.repo, -12)
        assert pr is None

    async def test_fetch_pull_request(self):
        pr = await self.execute(None, self.repo, self.pr.pullid)
        assert pr == self.pr
