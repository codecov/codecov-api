import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from core.models import PullStates
from core.tests.factories import OwnerFactory, PullFactory, RepositoryFactory
from internal_api import pull
from reports.tests.factories import UploadFactory

from ..fetch_pull_requests import FetchPullRequestsInteractor


class FetchPullRequestsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.pull_id = 10
        self.pull_title = "test-open-pr-1"
        self.org = OwnerFactory()
        self.repository_no_pull_requests = RepositoryFactory(
            author=self.org, private=False
        )
        self.repository_with_pull_requests = RepositoryFactory(
            author=self.org, private=False
        )
        PullFactory(
            pullid=self.pull_id,
            repository_id=self.repository_with_pull_requests.repoid,
            title=self.pull_title,
            state=PullStates.OPEN.value,
        )

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchPullRequestsInteractor(current_user, service).execute(*args)

    def test_fetch_when_repository_has_no_pulls(self):
        self.filters = None
        no_pull = async_to_sync(self.execute)(
            None, self.repository_no_pull_requests, self.filters
        )
        assert len(no_pull) is 0

    def test_fetch_when_repository_has_pulls(self):
        self.filters = None
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 1
        assert pull_request[0].pullid == self.pull_id
        assert pull_request[0].title == self.pull_title
        assert (
            pull_request[0].repository_id == self.repository_with_pull_requests.repoid
        )

    def test_fetch_when_repository_has_pulls_with_filters(self):
        # Add more pull requests with different states
        # 3 open, 2 closed, 1 merged
        PullFactory(
            pullid=20,
            repository_id=self.repository_with_pull_requests.repoid,
            title="test-open-pr-2",
            state=PullStates.OPEN.value,
        )
        PullFactory(
            pullid=21,
            repository_id=self.repository_with_pull_requests.repoid,
            title="test-open-pr-3",
            state=PullStates.OPEN.value,
        )
        PullFactory(
            pullid=30,
            repository_id=self.repository_with_pull_requests.repoid,
            title="test-closed-pr-1",
            state=PullStates.CLOSED.value,
        )
        PullFactory(
            pullid=31,
            repository_id=self.repository_with_pull_requests.repoid,
            title="test-closed-pr-2",
            state=PullStates.CLOSED.value,
        )
        PullFactory(
            pullid=40,
            repository_id=self.repository_with_pull_requests.repoid,
            title="test-merged-pr-1",
            state=PullStates.MERGED.value,
        )
        # Execute without filters
        self.filters = None
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 6

        # Execute without open filter
        self.filters = {"state": [PullStates.OPEN]}
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 3
        for pull in pull_request:
            assert pull.state == PullStates.OPEN.value

        # Execute without closed filter
        self.filters = {"state": [PullStates.CLOSED]}
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 2
        for pull in pull_request:
            assert pull.state == PullStates.CLOSED.value

        # Execute without merged filter
        self.filters = {"state": [PullStates.MERGED]}
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 1
        for pull in pull_request:
            assert pull.state == PullStates.MERGED.value

        # Execute without merged filter
        self.filters = {"state": [PullStates.MERGED, PullStates.OPEN]}
        pull_request = async_to_sync(self.execute)(
            None, self.repository_with_pull_requests, self.filters
        )
        assert len(pull_request) is 4
