from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory, SessionFactory

from .helper import GraphQLTestHelper, paginate_connection

query = """
query MySession {
  me {
    sessions {
      edges {
        node {
          name
          ip
          lastseen
          useragent
          type
          lastFour
        }
      }
    }
  }
}
"""


class SessionTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.session = SessionFactory(
            owner=self.owner,
            type="login",
            name="test-123",
            lastseen="2021-01-01T00:00:00+00:00",
        )

    @freeze_time("2021-01-01")
    def test_fetching_session(self):
        data = self.gql_request(query, owner=self.owner)
        sessions = paginate_connection(data["me"]["sessions"])
        current_session = self.owner.session_set.filter(type="login").first()
        assert sessions == [
            {
                "name": current_session.name,
                "ip": current_session.ip,
                "lastseen": "2021-01-01T00:00:00+00:00",
                "useragent": current_session.useragent,
                "type": current_session.type,
                "lastFour": str(current_session.token)[-4:],
            }
        ]

    def test_fetching_session_doesnt_include_other_people_session(self):
        random_user = OwnerFactory()
        for _ in range(5):
            SessionFactory(owner=random_user)
        data = self.gql_request(query, owner=self.owner)
        sessions = paginate_connection(data["me"]["sessions"])
        assert len(sessions) == 1
