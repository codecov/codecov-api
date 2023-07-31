import pytest
from django.test import Client
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory


class PageNumberPaginationTests(APITestCase):
    def setUp(self):
        pass

    def test_pagination_returned_page_size(self):
        self.owner = OwnerFactory(plan="users-free", plan_user_count=5)
        self.users = [
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
        ]

        client = Client()
        client.force_login(user=self.owner)

        url = reverse(
            "users-list",
            kwargs=dict(service=self.owner.service, owner_username=self.owner.username),
        )

        response = client.get(url, data={})
        assert response.data["total_pages"] == 1

        response = client.get(url, data={"page_size": "1"})
        assert response.data["total_pages"] == 3

        response = client.get(url, data={"page_size": "100"})
        assert response.data["total_pages"] == 1
