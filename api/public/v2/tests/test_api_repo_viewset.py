from datetime import timedelta
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from codecov.tests.base_test import InternalAPITest
from utils.test_utils import APIClient


@freeze_time("2022-01-01T00:00:00")
class RepoViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.commit = CommitFactory(
            repository=self.repo, timestamp=timezone.now() - timedelta(days=1)
        )
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

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
        data = res.json()

        # there's a SQL trigger that updates this - not sure how to test the value
        assert data["results"][0]["updatestamp"] is not None
        del data["results"][0]["updatestamp"]

        assert data == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "name": self.repo.name,
                    "private": True,
                    "author": {
                        "service": self.org.service,
                        "username": self.org.username,
                        "name": self.org.name,
                    },
                    "language": self.repo.language,
                    "branch": "main",
                    "active": False,
                    "activated": False,
                    "totals": {
                        "branches": 0,
                        "complexity": 0.0,
                        "complexity_ratio": 0,
                        "complexity_total": 0.0,
                        "coverage": 85.0,
                        "diff": 0,
                        "files": 3,
                        "hits": 17,
                        "lines": 20,
                        "methods": 0,
                        "misses": 3,
                        "partials": 0,
                        "sessions": 1,
                    },
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
        data = res.json()

        # there's a SQL trigger that updates this - not sure how to test the value
        assert data["updatestamp"] is not None
        del data["updatestamp"]

        assert data == {
            "name": self.repo.name,
            "private": True,
            "author": {
                "service": self.org.service,
                "username": self.org.username,
                "name": self.org.name,
            },
            "language": self.repo.language,
            "branch": "main",
            "active": False,
            "activated": False,
            "totals": {
                "branches": 0,
                "complexity": 0.0,
                "complexity_ratio": 0,
                "complexity_total": 0.0,
                "coverage": 85.0,
                "diff": 0,
                "files": 3,
                "hits": 17,
                "lines": 20,
                "methods": 0,
                "misses": 3,
                "partials": 0,
                "sessions": 1,
            },
        }
