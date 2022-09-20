from django.urls import reverse
from freezegun import freeze_time

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, RepositoryFactory

get_permissions_method = (
    "api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions"
)


@freeze_time("2022-01-01T00:00:00")
class BranchViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.user = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.branches = [
            BranchFactory(repository=self.repo, name="foo"),
            BranchFactory(repository=self.repo, name="bar"),
            BranchFactory(name="baz"),
        ]
        self.client.force_login(user=self.user)

    def test_list(self):
        res = self.client.get(
            reverse(
                "api-v2-branches-list",
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
                {"name": "foo", "updatestamp": "2022-01-01T00:00:00Z"},
                {"name": "bar", "updatestamp": "2022-01-01T00:00:00Z"},
            ],
            "total_pages": 1,
        }

    def test_retrieve(self):
        res = self.client.get(
            reverse(
                "api-v2-branches-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "name": self.branches[0].name,
                },
            )
        )
        assert res.status_code == 200
        assert res.data["name"] == self.branches[0].name
        assert res.data["head_commit"]["report"]
