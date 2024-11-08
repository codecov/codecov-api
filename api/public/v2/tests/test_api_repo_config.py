from unittest.mock import patch

from django.urls import reverse
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov.tests.base_test import InternalAPITest
from utils.test_utils import APIClient


@freeze_time("2022-01-01T00:00:00")
class RepoConfigViewTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_get(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self.client.get(
            reverse(
                "api-v2-repo-config",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "upload_token": self.repo.upload_token,
            "graph_token": self.repo.image_token,
        }

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_get_no_part_of_org(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.current_owner.organizations = []
        self.current_owner.save()

        res = self.client.get(
            reverse(
                "api-v2-repo-config",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert res.status_code == 403
        assert self.repo.upload_token not in str(res.content)
        assert self.repo.image_token not in str(res.content)
