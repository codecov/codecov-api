from internal_api import pull
from asgiref.sync import async_to_sync
import pytest
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import async_to_sync

from core.tests.factories import RepositoryFactory, PullFactory, OwnerFactory
from reports.tests.factories import ReportSessionFactory

from ..fetch_pull_requests import FetchPullRequestsInteractor


class FetchPullRequestsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.pull_id=10
        self.pull_title="test-pull-request"
        self.org = OwnerFactory()
        self.repository_with_pull_requests = RepositoryFactory(author=self.org, private=False)
        PullFactory(pullid=self.pull_id, repository_id=self.repository_with_pull_requests.repoid, title=self.pull_title)

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchPullRequestsInteractor(current_user, service).execute(*args)

    def test_fetch_when_repository_has_pulls(self):
        pull_request = async_to_sync(self.execute)(None, self.repository_with_pull_requests)
        assert len(pull_request) is 1
        assert pull_request[0].pullid == self.pull_id
        assert pull_request[0].title == self.pull_title
        assert pull_request[0].repository_id == self.repository_with_pull_requests.repoid