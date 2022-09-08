from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory, SessionFactory, UserTokenFactory

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
        }
      }
    }
  }
}
"""


class UserTokensTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

        self.token1 = UserTokenFactory(owner=self.user, name="token1")
        self.token2 = UserTokenFactory(owner=self.user, name="token2")
        self.token3 = UserTokenFactory(name="token3")

    def test_user_tokens(self):
        data = self.gql_request(query, user=self.user)
        tokens = paginate_connection(data["me"]["tokens"])
        assert tokens == [
            {
                "id": str(self.token2.external_id),
                "name": "token2",
                "type": "api",
                "lastFour": str(self.token2.token)[-4:],
            },
            {
                "id": str(self.token1.external_id),
                "name": "token1",
                "type": "api",
                "lastFour": str(self.token1.token)[-4:],
            },
        ]
