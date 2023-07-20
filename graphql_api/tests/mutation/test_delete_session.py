from ddf import G
from django.test import TransactionTestCase

from codecov_auth.models import Session
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
        G(Session, owner=self.owner)
        session = self.owner.session_set.first()
        sessionid = session.sessionid
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"sessionid": sessionid}}
        )
        assert data["deleteSession"] == None
        deleted_session = self.owner.session_set.filter(sessionid=sessionid).first()
        assert None == deleted_session
