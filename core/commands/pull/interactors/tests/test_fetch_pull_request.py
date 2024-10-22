from datetime import datetime

import pytest
from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from ..fetch_pull_request import FetchPullRequestInteractor


class FetchPullRequestInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.pr = PullFactory(repository_id=self.repo.repoid)

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return FetchPullRequestInteractor(owner, service).execute(*args)

    async def test_fetch_when_pull_request_doesnt_exist(self):
        pr = await self.execute(None, self.repo, -12)
        assert pr is None

    async def test_fetch_pull_request(self):
        pr = await self.execute(None, self.repo, self.pr.pullid)
        assert pr == self.pr


# Not part of the class because TransactionTestCase cannot be parametrized
@freeze_time("2024-07-01 12:00:00")
@pytest.mark.parametrize(
    "pr_state, updatestamp, expected",
    [
        pytest.param(
            "open", "2024-07-01 11:50:00", False, id="pr_open_recently_updated"
        ),
        pytest.param("merged", "2024-07-01 01:00:00", False, id="pr_merged"),
        pytest.param(
            "closed", "2024-07-01 11:50:00", False, id="pr_closed_recently_updated"
        ),
        pytest.param(
            "open", "2024-07-01 01:00:00", True, id="pr_open_not_recently_updated"
        ),
    ],
)
def test_fetch_pull_should_sync(pr_state, updatestamp, expected, db):
    repo = RepositoryFactory(private=False)
    pr = PullFactory(repository_id=repo.repoid, state=pr_state)
    repo.save()
    pr.save()  # This will change the updatestamp, so we need to set it again
    pr.updatestamp = datetime.fromisoformat(updatestamp).replace(tzinfo=None)
    should_sync = FetchPullRequestInteractor(
        repo.author, repo.service
    )._should_sync_pull(pr)
    assert pr.updatestamp == datetime.fromisoformat(updatestamp).replace(tzinfo=None)
    assert should_sync == expected


def test_fetch_pull_updatestamp_is_none(db):
    repo = RepositoryFactory(private=False)
    pr = PullFactory(repository_id=repo.repoid, state="open")
    repo.save()
    pr.save()
    pr.updatestamp = None
    should_sync = FetchPullRequestInteractor(
        repo.author, repo.service
    )._should_sync_pull(pr)
    assert pr.updatestamp is None
    assert should_sync == False
