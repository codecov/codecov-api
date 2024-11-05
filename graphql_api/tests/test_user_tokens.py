from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    OwnerFactory,
    UserTokenFactory,
)

from .helper import GraphQLTestHelper, paginate_connection

query = """
query {
  me {
    tokens {
      edges {
        node {
          id
          name
          type
          lastFour
          expiration
        }
      }
    }
  }
}
"""


class UserTokensTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

        self.token1 = UserTokenFactory(owner=self.owner, name="token1")
        self.token2 = UserTokenFactory(owner=self.owner, name="token2")
        self.token3 = UserTokenFactory(name="token3")

    def test_user_tokens(self):
        data = self.gql_request(query, owner=self.owner)
        tokens = paginate_connection(data["me"]["tokens"])
        assert tokens == [
            {
                "id": str(self.token2.external_id),
                "name": "token2",
                "type": "api",
                "lastFour": str(self.token2.token)[-4:],
                "expiration": None,
            },
            {
                "id": str(self.token1.external_id),
                "name": "token1",
                "type": "api",
                "lastFour": str(self.token1.token)[-4:],
                "expiration": None,
            },
        ]
