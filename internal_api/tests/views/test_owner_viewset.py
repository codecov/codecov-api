from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory


class OwnerViewSetTests(APITestCase):
    def _list(self, kwargs={}):
        if not kwargs:
            kwargs = {"service": self.service}
        return self.client.get(reverse("owners-list", kwargs=kwargs))

    def _retrieve(self, kwargs):
        return self.client.get(reverse("owners-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "bitbucket"
        self.user = OwnerFactory(stripe_customer_id=1000)

    def test_list_owners_returns_owners_for_service(self):
        bb_owner, gh_owner = OwnerFactory(service='bitbucket'), OwnerFactory(service='github')
        response = self._list()

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0] == {
            "service": bb_owner.service,
            "username": bb_owner.username,
            "email": bb_owner.email,
            "stats": bb_owner.cache["stats"],
            "avatar_url": bb_owner.avatar_url,
            "ownerid": bb_owner.ownerid,
            "integration_id": bb_owner.integration_id
        }

    def test_list_owners_unknown_service_returns_404(self):
        response = self._list(kwargs={"service": "not-real"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_returns_owner_with_username(self):
        owner = OwnerFactory()
        response = self._retrieve(kwargs={"service": owner.service, "username": owner.username})
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
           "service": owner.service,
           "username": owner.username,
           "email": owner.email,
           "stats": owner.cache["stats"],
           "avatar_url": owner.avatar_url,
           "ownerid": owner.ownerid,
           "integration_id": owner.integration_id
        }

    def test_retrieve_returns_404_if_no_matching_username(self):
        response = self._retrieve(kwargs={"service": "github", "username": "fff"})
        assert response.status_code == status.HTTP_404_NOT_FOUND
