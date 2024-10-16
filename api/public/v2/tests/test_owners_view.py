from django.test import TestCase
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import OwnerFactory

from utils.test_utils import APIClient


class OwnersViewTestCase(TestCase):
    def setUp(self):
        self.service = "github"
        self.org1 = OwnerFactory(username="org1", service=self.service)
        self.org2 = OwnerFactory(username="org2", service=self.service)
        self.org3 = OwnerFactory(username="org3", service=self.service)

        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org1.pk, self.org2.pk],
        )

    def _request_owners(self, service="github", login=True):
        if login:
            self.client = APIClient()
            self.client.force_login_owner(self.current_owner)
        url = reverse(
            "api-v2-service-owners",
            kwargs={
                "service": service,
            },
        )

        return self.client.get(url)

    def test_owners_list(self):
        res = self._request_owners()
        assert res.status_code == 200
        assert [item["username"] for item in res.json()["results"]] == [
            "org1",
            "org2",
            "codecov-user",
        ]

    def test_owners_list_invalid_service(self):
        res = self._request_owners(service="unknown")
        assert res.status_code == 404

    def test_owners_list_unauthenticated(self):
        res = self._request_owners(login=False)
        assert res.status_code == 401
