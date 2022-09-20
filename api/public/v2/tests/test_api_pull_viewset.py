from unittest.mock import patch

from django.urls import reverse
from freezegun import freeze_time

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import PullFactory, RepositoryFactory


@freeze_time("2022-01-01T00:00:00")
class PullViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.user = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.pulls = [
            PullFactory(repository=self.repo),
            PullFactory(repository=self.repo),
        ]
        self.client.force_login(user=self.user)

    def test_list(self):
        res = self.client.get(
            reverse(
                "api-v2-pulls-list",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": self.pulls[1].pullid,
                    "title": self.pulls[1].title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2022-01-01T00:00:00Z",
                    "state": "open",
                    "ci_passed": None,
                    "author": None,
                },
                {
                    "pullid": self.pulls[0].pullid,
                    "title": self.pulls[0].title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2022-01-01T00:00:00Z",
                    "state": "open",
                    "ci_passed": None,
                    "author": None,
                },
            ],
            "total_pages": 1,
        }

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_retrieve(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self.client.get(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "pullid": self.pulls[0].pullid,
            "title": self.pulls[0].title,
            "base_totals": None,
            "head_totals": None,
            "updatestamp": "2022-01-01T00:00:00Z",
            "state": "open",
            "ci_passed": None,
            "author": None,
        }
