from django.test import TransactionTestCase
from django.utils import timezone

from codecov_auth.models import DjangoSession, Session
from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: DeleteSessionInput!) {
  deleteSession(input: $input) {
    error {
      __typename
    }
  }
}
"""


class DeleteSessionTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"sessionid": 1}})
        assert data["deleteSession"]["error"]["__typename"] == "UnauthenticatedError"

    def test_when_authenticated(self):
        django_session = DjangoSession.objects.create(
            expire_date=timezone.now(),
            session_key="123abc",
        )
        sessionid = Session.objects.create(
            lastseen=timezone.now(),
            useragent="Firefox",
            ip="0.0.0.0",
            login_session=django_session,
            type=Session.SessionType.LOGIN,
            owner=self.owner,
        ).sessionid

        self.gql_request(
            query, owner=self.owner, variables={"input": {"sessionid": sessionid}}
        )

        assert len(DjangoSession.objects.filter(session_key="123abc")) == 0
        assert len(Session.objects.filter(sessionid=sessionid)) == 0
