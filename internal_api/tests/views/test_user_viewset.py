import pytest
from unittest.mock import patch
from ddf import G
import dateutil
from datetime import datetime

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status
from internal_api.tests.test_utils import GetAdminProviderAdapter

from codecov_auth.tests.factories import OwnerFactory, SessionFactory
from core.models import Pull, Repository


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(plan="users-free", plan_user_count=5)
        self.users = [
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
        ]

        self.client.force_login(user=self.owner)

    def _list(self, kwargs={}, query_params={}):
        if not kwargs:
            kwargs = {
                "service": self.owner.service,
                "owner_username": self.owner.username,
            }
        return self.client.get(reverse("users-list", kwargs=kwargs), data=query_params)

    def _patch(self, kwargs, data):
        return self.client.patch(reverse("users-detail", kwargs=kwargs), data=data)

    def test_list_returns_200_and_user_list_on_success(self):
        response = self._list()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {
                "name": user.name,
                "is_admin": False,
                "activated": False,
                "username": user.username,
                "email": user.email,
                "ownerid": user.ownerid,
                "student": user.student,
                "latest_private_pr_date": None,
                "lastseen": None,
            }
            for user in self.users
        ]

    @patch("codecov_auth.models.Owner.is_admin", lambda self, owner: False)
    @patch("internal_api.permissions.get_provider")
    def test_list_returns_403_if_user_not_admin(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        response = self._list()
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_sets_activated(self):
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._list()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][0] == {
            "name": self.users[0].name,
            "activated": True,
            "is_admin": False,
            "username": self.users[0].username,
            "email": self.users[0].email,
            "ownerid": self.users[0].ownerid,
            "student": self.users[0].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

    def test_list_sets_is_admin(self):
        self.owner.admins = [self.users[1].ownerid]
        self.owner.save()

        response = self._list()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"][1] == {
            "name": self.users[1].name,
            "activated": False,
            "is_admin": True,
            "username": self.users[1].username,
            "email": self.users[1].email,
            "ownerid": self.users[1].ownerid,
            "student": self.users[1].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

    def test_list_sets_latest_private_pr_date_in(self):
        pull = G(
            Pull,
            repository=G(Repository, author=self.owner, private=True),
            author=self.users[0],
        )

        response = self._list()
        assert (
            dateutil.parser.parse(response.data["results"][0]["latest_private_pr_date"], ignoretz=True)
            == pull.updatestamp
        )

    def test_list_sets_lastseen(self):
        session = SessionFactory(owner=self.users[0])
        response = self._list()
        assert (
            dateutil.parser.parse(response.data["results"][0]["lastseen"])
            == session.lastseen
        )

    def test_list_can_filter_by_activated(self):
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._list(query_params={"activated": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {
                "name": self.users[0].name,
                "activated": True,
                "is_admin": False,
                "username": self.users[0].username,
                "email": self.users[0].email,
                "ownerid": self.users[0].ownerid,
                "student": self.users[0].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            }
        ]

    def test_list_can_filter_by_is_admin(self):
        self.owner.admins = [self.users[1].ownerid]
        self.owner.save()

        response = self._list(query_params={"is_admin": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {
                "name": self.users[1].name,
                "activated": False,
                "is_admin": True,
                "username": self.users[1].username,
                "email": self.users[1].email,
                "ownerid": self.users[1].ownerid,
                "student": self.users[1].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            }
        ]

    def test_list_can_search_by_username(self):
        # set up some names
        self.users[0].username = "thanos"
        self.users[0].save()
        self.users[1].username = "thor23"
        self.users[1].save()
        self.users[2].username = "thor"
        self.users[2].save()

        response = self._list(query_params={"search": "hor"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {
                "name": self.users[1].name,
                "activated": False,
                "is_admin": False,
                "username": "thor23",
                "email": self.users[1].email,
                "ownerid": self.users[1].ownerid,
                "student": self.users[1].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
            {
                "name": self.users[2].name,
                "activated": False,
                "is_admin": False,
                "username": "thor",
                "email": self.users[2].email,
                "ownerid": self.users[2].ownerid,
                "student": self.users[2].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
        ]

    def test_list_can_search_by_name(self):
        # set up some names
        self.users[0].name = "thanos"
        self.users[0].save()
        self.users[1].name = "thor23"
        self.users[1].save()
        self.users[2].name = "thor"
        self.users[2].save()

        response = self._list(query_params={"search": "tho"})
        assert response.status_code == status.HTTP_200_OK
        expected_result = [
            {
                "name": "thor23",
                "activated": False,
                "is_admin": False,
                "username": self.users[1].username,
                "email": self.users[1].email,
                "ownerid": self.users[1].ownerid,
                "student": self.users[1].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
            {
                "name": "thor",
                "activated": False,
                "is_admin": False,
                "username": self.users[2].username,
                "email": self.users[2].email,
                "ownerid": self.users[2].ownerid,
                "student": self.users[2].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
        ]
        assert response.data["results"][0] == expected_result[0]
        assert response.data["results"][1] == expected_result[1]
        assert response.data["results"] == expected_result

    @pytest.mark.skip(reason="flaky, skipping until re write")
    def test_list_can_search_by_email(self):
        # set up some names
        self.users[0].email = "thanos@gmail.com"
        self.users[0].save()
        self.users[1].email = "ironman@gmail.com"
        self.users[1].save()
        self.users[2].email = "thor@gmail.com"
        self.users[2].save()

        response = self._list(query_params={"search": "th"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["results"] == [
            {
                "name": self.users[0].name,
                "activated": False,
                "is_admin": False,
                "username": self.users[0].username,
                "email": "thanos@gmail.com",
                "ownerid": self.users[0].ownerid,
                "student": self.users[0].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
            {
                "name": self.users[2].name,
                "activated": False,
                "is_admin": False,
                "username": self.users[2].username,
                "email": "thor@gmail.com",
                "ownerid": self.users[2].ownerid,
                "student": self.users[2].student,
                "latest_private_pr_date": None,
                "lastseen": None,
            },
        ]

    def test_list_can_order_by_name(self):
        self.users[0].name = "a"
        self.users[0].save()
        self.users[1].name = "b"
        self.users[1].save()
        self.users[2].name = "c"
        self.users[2].save()

        response = self._list(query_params={"ordering": "name"})

        assert [r["name"] for r in response.data["results"]] == ["a", "b", "c"]

        response = self._list(query_params={"ordering": "-name"})

        assert [r["name"] for r in response.data["results"]] == ["c", "b", "a"]

    def test_list_can_order_by_username(self):
        self.users[0].username = "a"
        self.users[0].save()
        self.users[1].username = "b"
        self.users[1].save()
        self.users[2].username = "c"
        self.users[2].save()

        response = self._list(query_params={"ordering": "username"})

        assert [r["username"] for r in response.data["results"]] == ["a", "b", "c"]

        response = self._list(query_params={"ordering": "-username"})

        assert [r["username"] for r in response.data["results"]] == ["c", "b", "a"]

    def test_list_can_order_by_email(self):
        self.users[0].email = "a"
        self.users[0].save()
        self.users[1].email = "b"
        self.users[1].save()
        self.users[2].email = "c"
        self.users[2].save()

        response = self._list(query_params={"ordering": "email"})

        assert [r["email"] for r in response.data["results"]] == ["a", "b", "c"]

        response = self._list(query_params={"ordering": "-email"})

        assert [r["email"] for r in response.data["results"]] == ["c", "b", "a"]

    def test_patch_can_set_activated_to_true(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username,
            },
            data={"activated": True},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "name": self.users[0].name,
            "activated": True,
            "is_admin": False,
            "username": self.users[0].username,
            "email": self.users[0].email,
            "ownerid": self.users[0].ownerid,
            "student": self.users[0].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

        self.owner.refresh_from_db()
        assert self.users[0].ownerid in self.owner.plan_activated_users

    def test_patch_can_set_activated_to_false(self):
        # setup activated user
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username,
            },
            data={"activated": False},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "name": self.users[0].name,
            "activated": False,
            "is_admin": False,
            "username": self.users[0].username,
            "email": self.users[0].email,
            "ownerid": self.users[0].ownerid,
            "student": self.users[0].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

        self.owner.refresh_from_db()
        assert self.users[0].ownerid not in self.owner.plan_activated_users

    @patch("services.segment.SegmentService.account_deactivated_user")
    @patch("services.segment.SegmentService.account_activated_user")
    def test_user_activation_or_deactivation_triggers_segment_events(
        self, activated_event_mock, deactivated_event_mock
    ):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username,
            },
            data={"activated": True},
        )

        activated_event_mock.assert_called_once_with(
            current_user_ownerid=self.owner.ownerid,
            ownerid_to_activate=self.users[0].ownerid,
            org_ownerid=self.owner.ownerid,
        )

        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username,
            },
            data={"activated": False},
        )

        deactivated_event_mock.assert_called_once_with(
            current_user_ownerid=self.owner.ownerid,
            ownerid_to_deactivate=self.users[0].ownerid,
            org_ownerid=self.owner.ownerid,
        )

    @patch("codecov_auth.models.Owner.can_activate_user", lambda self, user: False)
    def test_patch_returns_403_if_cannot_activate_user(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username,
            },
            data={"activated": True},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_can_set_is_admin_to_true(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[2].username,
            },
            data={"is_admin": True},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "name": self.users[2].name,
            "activated": False,
            "is_admin": True,
            "username": self.users[2].username,
            "email": self.users[2].email,
            "ownerid": self.users[2].ownerid,
            "student": self.users[2].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

        self.owner.refresh_from_db()
        assert self.users[2].ownerid in self.owner.admins

    def test_patch_can_set_is_admin_to_false(self):
        self.owner.admins = [self.users[2].ownerid]
        self.owner.save()

        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[2].username,
            },
            data={"is_admin": False},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "name": self.users[2].name,
            "activated": False,
            "is_admin": False,
            "username": self.users[2].username,
            "email": self.users[2].email,
            "ownerid": self.users[2].ownerid,
            "student": self.users[2].student,
            "latest_private_pr_date": None,
            "lastseen": None,
        }

        self.owner.refresh_from_db()
        assert self.users[2].ownerid not in self.owner.admins
