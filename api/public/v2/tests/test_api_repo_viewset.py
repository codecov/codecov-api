from unittest.mock import patch

from django.urls import reverse
from freezegun import freeze_time

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


@freeze_time("2022-01-01T00:00:00")
class RepoViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.user = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.client.force_login(user=self.user)

    def test_list(self):
        res = self.client.get(
            reverse(
                "api-v2-repos-list",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "repoid": self.repo.pk,
                    "name": self.repo.name,
                    "private": True,
                    "updatestamp": "2022-01-01T00:00:00Z",
                    "author": {
                        "service": self.org.service,
                        "username": self.org.username,
                        "name": self.org.name,
                    },
                    "language": self.repo.language,
                    "branch": "master",
                    "active": False,
                    "activated": False,
                }
            ],
            "total_pages": 1,
        }

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_retrieve(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self.client.get(
            reverse(
                "api-v2-repos-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "repoid": self.repo.pk,
            "name": self.repo.name,
            "private": True,
            "updatestamp": "2022-01-01T00:00:00Z",
            "author": {
                "service": self.org.service,
                "username": self.org.username,
                "name": self.org.name,
            },
            "language": self.repo.language,
            "branch": "master",
            "active": False,
            "activated": False,
        }
