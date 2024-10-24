from django.contrib import auth
from django.test import TransactionTestCase
from django.utils import timezone
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory, UserFactory

from codecov_auth.models import DjangoSession, Session
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
        user = UserFactory()
        self.owner.user = user
        self.owner.save()

        login_query = "{ me { user { username }} }"
        self.gql_request(login_query, owner=self.owner)

        user = auth.get_user(self.client)
        assert user.is_authenticated

        django_session_id = DjangoSession.objects.all()
        assert len(django_session_id) == 1

        django_session_id = django_session_id[0]

        sessionid = Session.objects.create(
            lastseen=timezone.now(),
            useragent="Firefox",
            ip="0.0.0.0",
            login_session=django_session_id,
            type=Session.SessionType.LOGIN,
            owner=self.owner,
        ).sessionid

        self.gql_request(
            query, owner=self.owner, variables={"input": {"sessionid": sessionid}}
        )
        assert len(Session.objects.filter(sessionid=sessionid)) == 0

    def test_when_authenticated_session_not_valid(self):
        user = UserFactory()
        self.owner.user = user
        self.owner.save()

        login_query = "{ me { user { username }} }"
        self.gql_request(login_query, owner=self.owner)

        user = auth.get_user(self.client)
        assert user.is_authenticated

        django_session_id = DjangoSession.objects.all()
        assert len(django_session_id) == 1

        django_session_id = django_session_id[0]

        Session.objects.create(
            lastseen=timezone.now(),
            useragent="Firefox",
            ip="0.0.0.0",
            login_session=django_session_id,
            type=Session.SessionType.LOGIN,
            owner=self.owner,
        ).sessionid

        self.gql_request(query, owner=self.owner, variables={"input": {"sessionid": 0}})
        assert len(Session.objects.all()) == 1
