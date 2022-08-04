import datetime
from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from .helper import GraphQLTestHelper, paginate_connection


class ArianeTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user", name="codecov-name")
        self.user2 = OwnerFactory(username="codecov-user", name=None)

        random_user = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.user, active=True, private=True, name="a")
        RepositoryFactory(author=self.user, active=True, private=True, name="b")
        RepositoryFactory(author=random_user, active=True, private=True, name="not")
        self.user.organizations = [
            OwnerFactory(username="codecov").ownerid,
            OwnerFactory(username="facebook").ownerid,
            OwnerFactory(username="spotify").ownerid,
        ]
        self.user.save()
        self.user2.save()

    @patch("jwt.encode")
    def test_canny_sso_token_gen_provided_name(self, mock_jwt):
        user_data = {
            "avatarURL": self.user.avatar_url,
            "email": self.user.email,
            "id": self.user.ownerid,
            "name": self.user.name,
        }

        query = "{ me { user { cannySSOToken } } }"
        data = self.gql_request(query, user=self.user)
        mock_jwt.assert_called_once_with(user_data, "", algorithm="HS256")

    @patch("jwt.encode")
    def test_canny_sso_token_gen_no_name(self, mock_jwt):
        user_data = {
            "avatarURL": self.user2.avatar_url,
            "email": self.user2.email,
            "id": self.user2.ownerid,
            "name": self.user2.username,
        }

        query = "{ me { user { cannySSOToken } } }"
        data = self.gql_request(query, user=self.user2)
        mock_jwt.assert_called_once_with(user_data, "", algorithm="HS256")
