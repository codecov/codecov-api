from unittest.mock import patch

from django.test import TestCase
from rest_framework.reverse import reverse

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class FlagViewSetTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )
        self.flag1 = RepositoryFlagFactory(flag_name="foo", repository=self.repo)
        self.flag2 = RepositoryFlagFactory(flag_name="bar", repository=self.repo)
        self.flag2 = RepositoryFlagFactory(flag_name="baz")

    def _request_flags(self):
        self.client.force_login(user=self.user)
        url = reverse(
            "api-v2-flags-list",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        return self.client.get(url)

    def test_flag_list(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self._request_flags()
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [{"flag_name": "foo"}, {"flag_name": "bar"}],
            "total_pages": 1,
        }
