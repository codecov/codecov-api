from unittest.mock import patch

from django.test import TestCase
from rest_framework.reverse import reverse

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from services.components import Component


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class ComponentViewSetTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.commit = CommitFactory(repository=self.repo)
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )

    def _request_components(self):
        self.client.force_login(user=self.user)
        url = reverse(
            "api-v2-components-list",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        return self.client.get(url)

    @patch("api.public.v2.component.views.commit_components")
    def test_component_list(self, commit_compontents, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        commit_compontents.return_value = [
            Component(
                component_id="foo",
                paths=[r".*foo"],
                name="Foo",
                flag_regexes=[],
                statuses=[],
            ),
            Component(
                component_id="bar",
                paths=[r".*bar"],
                name="Bar",
                flag_regexes=[],
                statuses=[],
            ),
        ]

        res = self._request_components()
        assert res.status_code == 200
        assert res.json() == [
            {"component_id": "foo", "name": "Foo"},
            {"component_id": "bar", "name": "Bar"},
        ]
