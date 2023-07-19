import datetime
from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from .helper import GraphQLTestHelper, paginate_connection


class ArianeTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user", name="codecov-name")
        self.owner2 = OwnerFactory(username="codecov-user", name=None)

        random_user = OwnerFactory(username="random-user")
        RepositoryFactory(author=self.owner, active=True, private=True, name="a")
        RepositoryFactory(author=self.owner, active=True, private=True, name="b")
        RepositoryFactory(author=random_user, active=True, private=True, name="not")
        self.owner.organizations = [
            OwnerFactory(username="codecov").ownerid,
            OwnerFactory(username="facebook").ownerid,
            OwnerFactory(username="spotify").ownerid,
        ]
        self.owner.save()
        self.owner2.save()

    @patch("jwt.encode")
    def test_canny_sso_token_gen_provided_name(self, mock_jwt):
        user_data = {
            "avatarURL": self.owner.avatar_url,
            "email": self.owner.email,
            "id": self.owner.ownerid,
            "name": self.owner.name,
        }

        query = "{ me { user { cannySSOToken } } }"
        data = self.gql_request(query, owner=self.owner)
        mock_jwt.assert_called_once_with(user_data, "", algorithm="HS256")

    @patch("jwt.encode")
    def test_canny_sso_token_gen_no_name(self, mock_jwt):
        user_data = {
            "avatarURL": self.owner2.avatar_url,
            "email": self.owner2.email,
            "id": self.owner2.ownerid,
            "name": self.owner2.username,
        }

        query = "{ me { user { cannySSOToken } } }"
        data = self.gql_request(query, owner=self.owner2)
        mock_jwt.assert_called_once_with(user_data, "", algorithm="HS256")
