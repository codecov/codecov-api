from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from utils.test_utils import Client


class PageNumberPaginationTests(APITestCase):
    def setUp(self):
        self.client = Client()
        self.owner = OwnerFactory(plan="users-free", plan_user_count=5)
        self.users = [
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
        ]

    def test_pagination_returned_page_size(self):
        self.client.force_login_owner(self.owner)

        def _list(kwargs={}, query_params={}):
            if not kwargs:
                kwargs = {
                    "service": self.owner.service,
                    "owner_username": self.owner.username,
                }
            return self.client.get(
                reverse("users-list", kwargs=kwargs), data=query_params
            )

        response = _list()

        assert response.data["total_pages"] == 1

        response = _list(query_params={"page_size": "1"})

        assert response.data["total_pages"] == 3

        response = _list(query_params={"page_size": "100"})

        assert response.data["total_pages"] == 1
