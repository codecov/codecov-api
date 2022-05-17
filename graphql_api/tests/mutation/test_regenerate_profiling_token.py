from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RegenerateProfilingTokenInput!) {
  regenerateProfilingToken(input: $input) {
    profilingToken
    error {
      __typename
    }
  }
}
"""


class RegenerateProfilingToken(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(name="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo")

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query, variables={"input": {"repoName": "gazebo", "owner": "codecov"}}
        )
        assert (
            data["regenerateProfilingToken"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    def test_when_validation_error_repo_not_viewable(self):
        random_user = OwnerFactory(organizations=[self.org.ownerid])
        data = self.gql_request(
            query,
            user=random_user,
            variables={"input": {"repoName": "gazebo", "owner": "codecov"}},
        )
        assert (
            data["regenerateProfilingToken"]["error"]["__typename"] == "ValidationError"
        )

    def test_when_authenticated_regenerate_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )
        RepositoryTokenFactory(repository=self.repo, key="random")
        data = self.gql_request(
            query,
            user=user,
            variables={"input": {"owner": "codecov", "repoName": "gazebo"}},
        )
        newToken = data["regenerateProfilingToken"]["profilingToken"]
        assert newToken != "random"
        assert len(newToken) == 40
