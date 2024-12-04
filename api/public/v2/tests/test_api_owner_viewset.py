from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ErrorDetail
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory, SessionFactory

from codecov_auth.tests.factories import DjangoSessionFactory
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

    def _patch(self, kwargs, data):
        return self.client.patch(
            reverse("api-v2-users-detail", kwargs=kwargs), data=data
        )

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

    def test_update_activate_by_username(self):
        another_user = OwnerFactory(service="github", organizations=[self.org.pk])

        # Activate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": True,
            "is_admin": False,
            "email": another_user.email,
        }

        # Deactivate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
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

    def test_update_activate_by_ownerid(self):
        another_user = OwnerFactory(service="github", organizations=[self.org.pk])

        # Activate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.ownerid,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": True,
            "is_admin": False,
            "email": another_user.email,
        }

        # Deactivate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.ownerid,
            },
            data={"activated": False},
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

    def test_update_activate_unauthorized_members_of_other_orgs(self):
        another_org = OwnerFactory(service="github")
        another_user = OwnerFactory(service="github", organizations=[another_org.pk])

        # Activate user - not allowed
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Deactivate user - not allowed
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Request allowed after user joins the org
        another_user.organizations.append(self.org.pk)
        another_user.save()

        # Activate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": True,
            "is_admin": False,
            "email": another_user.email,
        }

        # Deactivate user
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
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

    def test_update_activate_unauthorized_not_member_of_org(self):
        another_org = OwnerFactory(service="github")
        another_user = OwnerFactory(service="github", organizations=[another_org.pk])

        # Activate user - not allowed
        response = self._patch(
            kwargs={
                "service": another_org.service,
                "owner_username": another_org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Deactivate user - not allowed
        response = self._patch(
            kwargs={
                "service": another_org.service,
                "owner_username": another_org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # Request owner now joins the other org and thus is allowed to activate/deactivate
        self.current_owner.organizations.append(another_org.pk)
        self.current_owner.save()

        # Activate user
        response = self._patch(
            kwargs={
                "service": another_org.service,
                "owner_username": another_org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": True,
            "is_admin": False,
            "email": another_user.email,
        }

        # Deactivate user
        response = self._patch(
            kwargs={
                "service": another_org.service,
                "owner_username": another_org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
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

    def test_update_activate_no_seats_left(self):
        another_user = OwnerFactory(service="github", organizations=[self.org.pk])
        another_user_2 = OwnerFactory(service="github", organizations=[self.org.pk])

        # Activate user 1
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user.username,
            "name": another_user.name,
            "activated": True,
            "is_admin": False,
            "email": another_user.email,
        }

        # Activate user 2
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user_2.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "detail": ErrorDetail(
                string="Cannot activate user -- not enough seats left.",
                code="no_seats_left",
            )
        }

        # Deactivate user 1 to make room for user 2
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user.username,
            },
            data={"activated": False},
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

        # Activate user 2 now that there's room
        response = self._patch(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "user_username_or_ownerid": another_user_2.username,
            },
            data={"activated": True},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "service": "github",
            "username": another_user_2.username,
            "name": another_user_2.name,
            "activated": True,
            "is_admin": False,
            "email": another_user_2.email,
        }


class UserSessionViewSetTests(APITestCase):
    def _list(self, kwargs):
        return self.client.get(reverse("api-v2-user-sessions-list", kwargs=kwargs))

    def setUp(self):
        self.org = OwnerFactory(service="github")
        self.admin_owner = OwnerFactory(service="github", organizations=[self.org.pk])
        self.org.admins = [self.admin_owner.pk]
        self.org.save()
        self.client = APIClient()

    def test_not_part_of_org(self):
        self.current_owner = OwnerFactory(service="github", organizations=[])
        self.client.force_login_owner(self.current_owner)

        response = self._list(
            kwargs={"service": self.org.service, "owner_username": self.org.username}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_not_admin_of_org(self):
        self.not_in_org_owner = OwnerFactory(
            service="github", organizations=[self.org.pk]
        )
        self.client.force_login_owner(self.not_in_org_owner)

        response = self._list(
            kwargs={"service": self.org.service, "owner_username": self.org.username}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_no_sessions(self):
        self.client.force_login_owner(self.admin_owner)

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
                    "username": self.admin_owner.username,
                    "name": self.admin_owner.name,
                    "has_active_session": False,
                    "expiry_date": None,
                }
            ],
            "total_pages": 1,
        }

    def test_has_active_session(self):
        expiry_date = timezone.now() + timedelta(days=1)
        expiry_date_response = str(expiry_date).replace(" ", "T").replace("+00:00", "Z")

        self.session = SessionFactory(
            owner=self.admin_owner,
            login_session=DjangoSessionFactory(expire_date=expiry_date),
        )
        self.client.force_login_owner(self.admin_owner)

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
                    "username": self.admin_owner.username,
                    "name": self.admin_owner.name,
                    "has_active_session": True,
                    "expiry_date": expiry_date_response,
                }
            ],
            "total_pages": 1,
        }

    def test_multiple_sessions_one(self):
        expiry_date = timezone.now() + timedelta(days=1)
        expiry_date_response = str(expiry_date).replace(" ", "T").replace("+00:00", "Z")

        self.session_1 = SessionFactory(
            owner=self.admin_owner,
            login_session=DjangoSessionFactory(expire_date=expiry_date),
        )
        self.session_2 = SessionFactory(
            owner=self.admin_owner,
            login_session=DjangoSessionFactory(
                expire_date=timezone.now() - timedelta(days=1)
            ),
        )
        self.client.force_login_owner(self.admin_owner)

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
                    "username": self.admin_owner.username,
                    "name": self.admin_owner.name,
                    "has_active_session": True,
                    "expiry_date": expiry_date_response,
                }
            ],
            "total_pages": 1,
        }

    def test_multiple_sessions_two(self):
        expiry_date = timezone.now()
        expiry_date_response = str(expiry_date).replace(" ", "T").replace("+00:00", "Z")

        self.session_1 = SessionFactory(
            owner=self.admin_owner,
            login_session=DjangoSessionFactory(expire_date=expiry_date),
        )
        self.session_2 = SessionFactory(
            owner=self.admin_owner,
            login_session=DjangoSessionFactory(
                expire_date=timezone.now() - timedelta(days=1)
            ),
        )
        self.client.force_login_owner(self.admin_owner)

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
                    "username": self.admin_owner.username,
                    "name": self.admin_owner.name,
                    "has_active_session": False,
                    "expiry_date": expiry_date_response,
                }
            ],
            "total_pages": 1,
        }
