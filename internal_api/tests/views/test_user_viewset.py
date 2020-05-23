from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory()
        self.users = [
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid]),
            OwnerFactory(organizations=[self.owner.ownerid])
        ]

        self.client.force_login(user=self.owner)

    def _list(self, kwargs={}, query_params={}):
        if not kwargs:
            kwargs = {"service": self.owner.service, "username": self.owner.username}
        return self.client.get(reverse('users-list', kwargs=kwargs), data=query_params)

    def test_list_returns_200_and_user_list_on_success(self):
        response = self._list()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [
            {
                'name': user.name,
                'activated': False,
                'username': user.username,
                'email': user.email,
                'ownerid': user.ownerid,
                'student': user.student
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
            'username': self.users[0].username,
            'email': self.users[0].email,
            'ownerid': self.users[0].ownerid,
            'student': self.users[0].student
        }

    def test_list_can_filter_by_activated(self):
        self.owner.plan_activated_users = [self.users[0].ownerid]
        self.owner.save()

        response = self._list(query_params={"activated": True})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == [
            {
                'name': self.users[0].name,
                'activated': True,
                'username': self.users[0].username,
                'email': self.users[0].email,
                'ownerid': self.users[0].ownerid,
                'student': self.users[0].student
            }
        ]

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
                'username': self.users[1].username,
                'email': self.users[1].email,
                'ownerid': self.users[1].ownerid,
                'student': self.users[1].student
            },
            {
                'name': 'fero',
                'activated': False,
                'username': self.users[2].username,
                'email': self.users[2].email,
                'ownerid': self.users[2].ownerid,
                'student': self.users[2].student
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
