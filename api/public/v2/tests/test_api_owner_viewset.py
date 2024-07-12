from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from utils.test_utils import APIClient


class OwnerViewSetTests(APITestCase):
    def _retrieve(self, kwargs):
        return self.client.get(reverse("api-v2-owners-detail", kwargs=kwargs))

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
        assert response.data == {
            "detail": ErrorDetail(
                string="No Owner matches the given query.", code="not_found"
            )
        }

    def test_retrieve_owner_unknown_service_returns_404(self):
        response = self._retrieve(
            kwargs={"service": "not-real", "owner_username": "anything"}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"detail": "Service not found: not-real"}


class UserViewSetTests(APITestCase):
    def _list(self, kwargs):
        return self.client.get(reverse("api-v2-users-list", kwargs=kwargs))

    def _detail(self, kwargs):
        return self.client.get(reverse("api-v2-users-detail", kwargs=kwargs))

    def setUp(self):
        self.org = OwnerFactory(service="github")
        self.current_owner = OwnerFactory(service="github", organizations=[self.org.pk])
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

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
                    "username": self.current_owner.username,
                    "name": self.current_owner.name,
                    "activated": False,
                    "is_admin": False,
                    "email": self.current_owner.email,
                }
            ],
            "total_pages": 1,
        }

    def test_retrieve_by_username(self):
        another_user = OwnerFactory(service="github", organizations=[self.org.pk])
        response = self._detail(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": False,
            "is_admin": False,
            "email": another_user.email,
        }

    def test_retrieve_by_ownerid(self):
        another_user = OwnerFactory(service="github", organizations=[self.org.pk])
        response = self._detail(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.ownerid,
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": False,
            "is_admin": False,
            "email": another_user.email,
        }

    def test_retrieve_cannot_get_details_of_members_of_other_orgs(self):
        another_org = OwnerFactory(service="github")
        another_user = OwnerFactory(service="github", organizations=[another_org.pk])
        kwargs = {
            "service": self.org.service,
            "owner_username": self.org.username,
            "user_username_or_ownerid": another_user.username,
        }
        response = self._detail(kwargs=kwargs)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        another_user.organizations.append(self.org.pk)
        another_user.save()

        response = self._detail(kwargs=kwargs)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": False,
            "is_admin": False,
            "email": another_user.email,
        }

    def test_retrieve_cannot_get_details_if_not_member_of_org(self):
        another_org = OwnerFactory(service="github")
        another_user = OwnerFactory(service="github", organizations=[another_org.pk])
        kwargs = {
            "service": another_org.service,
            "owner_username": another_org.username,
            "user_username_or_ownerid": another_user.username,
        }
        response = self._detail(kwargs=kwargs)
        assert response.status_code == status.HTTP_404_NOT_FOUND

        self.current_owner.organizations.append(another_org.pk)
        self.current_owner.save()

        response = self._detail(kwargs=kwargs)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": False,
            "is_admin": False,
            "email": another_user.email,
        }
