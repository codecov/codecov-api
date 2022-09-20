from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory


class OwnerViewSetTests(APITestCase):
    def _retrieve(self, kwargs):
        return self.client.get(reverse("api-v2-owners-detail", kwargs=kwargs))

    def setUp(self):
        self.user = OwnerFactory(service="github", stripe_customer_id=1000)

    def test_retrieve_returns_owner_with_username(self):
        owner = OwnerFactory()
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
        }

    def test_retrieve_returns_owner_with_period_username(self):
        owner = OwnerFactory(username="codecov.test")
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
        }

    def test_retrieve_returns_404_if_no_matching_username(self):
        response = self._retrieve(kwargs={"service": "github", "owner_username": "fff"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"detail": "Not found."}

    def test_retrieve_owner_unknown_service_returns_404(self):
        response = self._retrieve(
            kwargs={"service": "not-real", "owner_username": "anything"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"detail": "Service not found: not-real"}


class UserViewSetTests(APITestCase):
    def _list(self, kwargs):
        return self.client.get(reverse("api-v2-users-list", kwargs=kwargs))

    def setUp(self):
        self.org = OwnerFactory(service="github")
        self.user = OwnerFactory(service="github", organizations=[self.org.pk])
        self.client.force_authenticate(user=self.user)

    def test_list(self):
        response = self._list(
            kwargs={"service": self.org.service, "owner_username": self.org.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "service": "github",
                    "username": self.user.username,
                    "name": self.user.name,
                    "activated": False,
                    "is_admin": False,
                    "email": self.user.email,
                }
            ],
            "total_pages": 1,
        }
