from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory


class OwnerViewSetTests(APITestCase):
    def _retrieve(self, kwargs):
        return self.client.get(reverse("owners-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "bitbucket"
        self.user = OwnerFactory(service="github", stripe_customer_id=1000)

    def test_retrieve_returns_owner_with_username(self):
        owner = OwnerFactory()
        response = self._retrieve(
            kwargs={"service": owner.service, "username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": owner.service,
            "username": owner.username,
            "name": owner.name,
            "stats": owner.cache["stats"],
            "avatar_url": owner.avatar_url,
            "ownerid": owner.ownerid,
            "integration_id": owner.integration_id,
        }

    def test_retrieve_returns_404_if_no_matching_username(self):
        response = self._retrieve(kwargs={"service": "github", "username": "fff"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"detail": "Not found."}

    def test_retrieve_owner_unknown_service_returns_404(self):
        response = self._retrieve(
            kwargs={"service": "not-real", "username": "anything"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"detail": "Service not found: not-real"}
