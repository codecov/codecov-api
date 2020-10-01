from unittest.mock import patch
from ddf import G
import dateutil
from datetime import datetime

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory, SessionFactory
from core.models import Pull, Repository


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(plan='users-free', plan_user_count=5)
        self.users = [
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid])
        ]

        self.client.force_login(user=self.owner)

    def _list(self, kwargs={}, query_params={}):
        if not kwargs:
            kwargs = {"service": self.owner.service, "owner_username": self.owner.username}
        return self.client.get(reverse('users-list', kwargs=kwargs), data=query_params)

    def _patch(self, kwargs, data):
        return self.client.patch(reverse('users-detail', kwargs=kwargs), data=data)

    def test_list_returns_200_and_user_list_on_success(self):
        response = self._list()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [
            {
                'name': user.name,
                'is_admin': False,
                'activated': False,
                'username': user.username,
                'email': user.email,
                'ownerid': user.ownerid,
                'student': user.student,
                'latest_private_pr_date': None,
                'lastseen': None
            }
            for user in self.users
        ]

    @patch('codecov_auth.models.Owner.is_admin', lambda self, owner: False)
    def test_list_returns_403_if_user_not_admin(self):
        response = self._list()
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_sets_activated(self):
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._list()

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'][0] == {
            'name': self.users[0].name,
            'activated': True,
            'is_admin': False,
            'username': self.users[0].username,
            'email': self.users[0].email,
            'ownerid': self.users[0].ownerid,
            'student': self.users[0].student,
            'latest_private_pr_date': None,
            'lastseen': None
        }

    def test_list_sets_is_admin(self):
        self.owner.admins = [self.users[1].ownerid]
        self.owner.save()

        response = self._list()

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'][1] == {
            'name': self.users[1].name,
            'activated': False,
            'is_admin': True,
            'username': self.users[1].username,
            'email': self.users[1].email,
            'ownerid': self.users[1].ownerid,
            'student': self.users[1].student,
            'latest_private_pr_date': None,
            'lastseen': None
        }

    def test_list_sets_latest_private_pr_date_in(self):
        pull = G(
            Pull,
            repository=G(Repository, author=self.owner, private=True),
            author=self.users[0]
        )

        response = self._list()
        assert dateutil.parser.parse(response.data["results"][0]["latest_private_pr_date"]) == pull.updatestamp

    def test_list_sets_lastseen(self):
        session = SessionFactory(owner=self.users[0])
        response = self._list()
        assert dateutil.parser.parse(response.data["results"][0]["lastseen"]) == session.lastseen

    def test_list_can_filter_by_activated(self):
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._list(query_params={"activated": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [
            {
                'name': self.users[0].name,
                'activated': True,
                'is_admin': False,
                'username': self.users[0].username,
                'email': self.users[0].email,
                'ownerid': self.users[0].ownerid,
                'student': self.users[0].student,
                'latest_private_pr_date': None,
                'lastseen': None
            }
        ]

    def test_list_can_filter_by_is_admin(self):
        self.owner.admins = [self.users[1].ownerid]
        self.owner.save()

        response = self._list(query_params={"is_admin": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [{
            'name': self.users[1].name,
            'activated': False,
            'is_admin': True,
            'username': self.users[1].username,
            'email': self.users[1].email,
            'ownerid': self.users[1].ownerid,
            'student': self.users[1].student,
            'latest_private_pr_date': None,
            'lastseen': None
        }]

    def test_list_can_filter_by_name_prefix(self):
        # set up some names
        self.users[0].name = "fe"
        self.users[0].save()
        self.users[1].name = "fer"
        self.users[1].save()
        self.users[2].name = "fero"
        self.users[2].save()

        response = self._list(query_params={"prefix": "fer"})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [
            {
                'name': 'fer',
                'activated': False,
                'is_admin': False,
                'username': self.users[1].username,
                'email': self.users[1].email,
                'ownerid': self.users[1].ownerid,
                'student': self.users[1].student,
                'latest_private_pr_date': None,
                'lastseen': None
            },
            {
                'name': 'fero',
                'activated': False,
                'is_admin': False,
                'username': self.users[2].username,
                'email': self.users[2].email,
                'ownerid': self.users[2].ownerid,
                'student': self.users[2].student,
                'latest_private_pr_date': None,
                'lastseen': None
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

        assert [r['name'] for r in response.data['results']] == ['a', 'b', 'c']

        response = self._list(query_params={"ordering": "-name"})

        assert [r['name'] for r in response.data['results']] == ['c', 'b', 'a']

    def test_patch_can_set_activated_to_true(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username
            },
            data={
                'activated': True
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'name': self.users[0].name,
            'activated': True,
            'is_admin': False,
            'username': self.users[0].username,
            'email': self.users[0].email,
            'ownerid': self.users[0].ownerid,
            'student': self.users[0].student,
            'latest_private_pr_date': None,
            'lastseen': None
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
                "user_username": self.users[0].username
            },
            data={
                'activated': False
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'name': self.users[0].name,
            'activated': False,
            'is_admin': False,
            'username': self.users[0].username,
            'email': self.users[0].email,
            'ownerid': self.users[0].ownerid,
            'student': self.users[0].student,
            'latest_private_pr_date': None,
            'lastseen': None
        }

        self.owner.refresh_from_db()
        assert self.users[0].ownerid not in self.owner.plan_activated_users

    @patch('codecov_auth.models.Owner.can_activate_user', lambda self, user: False)
    def test_patch_returns_403_if_cannot_activate_user(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[0].username
            },
            data={
                'activated': True
            }
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_patch_can_set_is_admin_to_true(self):
        response = self._patch(
            kwargs={
                "service": self.owner.service,
                "owner_username": self.owner.username,
                "user_username": self.users[2].username
            },
            data={
                'is_admin': True
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'name': self.users[2].name,
            'activated': False,
            'is_admin': True,
            'username': self.users[2].username,
            'email': self.users[2].email,
            'ownerid': self.users[2].ownerid,
            'student': self.users[2].student,
            'latest_private_pr_date': None,
            'lastseen': None
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
                "user_username": self.users[2].username
            },
            data={
                'is_admin': False
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            'name': self.users[2].name,
            'activated': False,
            'is_admin': False,
            'username': self.users[2].username,
            'email': self.users[2].email,
            'ownerid': self.users[2].ownerid,
            'student': self.users[2].student,
            'latest_private_pr_date': None,
            'lastseen': None
        }

        self.owner.refresh_from_db()
        assert self.users[2].ownerid not in self.owner.admins
