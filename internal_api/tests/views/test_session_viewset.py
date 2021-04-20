from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import SessionFactory, OwnerFactory
from codecov_auth.models import Session

from internal_api.tests.test_utils import to_drf_datetime_str
from internal_api.tests.test_utils import GetAdminProviderAdapter


class SessionViewSetTests(APITestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.user = OwnerFactory(organizations=[self.org.ownerid])

        self.org.admins = [self.user.ownerid]
        self.org.save()

        self.session = SessionFactory(owner=self.user, ip="127.0.0.1")

        self.client.force_login(self.user)

    def _list(self, kwargs={}):
        if not kwargs:
            kwargs = {"owner_username": self.org.username, "service": self.org.service}
        return self.client.get(reverse("sessions-list", kwargs=kwargs))

    def _create(self, kwargs={}, data={}):
        if not kwargs:
            kwargs = {"owner_username": self.org.username, "service": self.org.service}
        if not data:
            data = {
                "name": "an-api-session",
                "type": Session.SessionType.API,
                "owner": self.user.ownerid,
            }
        return self.client.post(reverse("sessions-list", kwargs=kwargs), data=data)

    def _delete(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "owner_username": self.org.username,
                "service": self.org.service,
                "pk": self.session.sessionid,
            }
        return self.client.delete(reverse("sessions-detail", kwargs=kwargs))

    def test_list_sessions_returns_200_and_session_data(self):
        response = self._list()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0] == {
            "sessionid": self.session.sessionid,
            "ip": self.session.ip,
            "useragent": self.session.useragent,
            "lastseen": to_drf_datetime_str(self.session.lastseen),
            "owner": self.session.owner.ownerid,
            "name": self.session.name,
            "type": self.session.type,
            "owner_info": {
                "avatar_url": self.user.avatar_url,
                "service": self.user.service,
                "username": self.user.username,
                "name": self.user.name,
                "stats": self.user.cache["stats"],
                "ownerid": self.user.ownerid,
                "integration_id": self.user.integration_id,
            },
        }

    def test_delete_session_returns_204_and_deletes_session(self):
        response = self._delete()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert Session.objects.all().count() == 0

    @patch("internal_api.permissions.get_provider")
    def test_list_requires_admin_rights(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        self.org.admins = None
        self.org.save()

        response = self._list()
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @patch("internal_api.permissions.get_provider")
    def test_delete_requires_admin_rights(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        self.org.admins = None
        self.org.save()

        response = self._delete()
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_returns_201_and_session_with_token(self):
        response = self._create()
        assert response.data.get("token") is not None

    def test_create_returns_400_for_other_owner_and_session_with_token(self):
        otherowner = OwnerFactory()
        import pdb

        pdb.set_trace()
        response = self._create(
            data={
                "name": "an-api-session",
                "type": Session.SessionType.API,
                "owner": otherowner.ownerid,
            }
        )
        assert response.data.get("token") is not None

    def test_create_required_fields(self):
        with self.subTest("missing name"):
            response = self._create(
                data={"type": Session.SessionType.API, "owner": self.user.ownerid}
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        with self.subTest("missing type"):
            response = self._create(
                data={"name": "api-token", "owner": self.user.ownerid}
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        with self.subTest("non-api type"):
            response = self._create(
                data={
                    "name": "api-token",
                    "type": Session.SessionType.LOGIN,
                    "owner": self.user.ownerid,
                }
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

        with self.subTest("missing owner"):
            response = self._create(
                data={"name": "api-token", "type": Session.SessionType.API}
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
