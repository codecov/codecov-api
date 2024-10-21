from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RegenerateRepositoryTokenInput!) {
  regenerateRepositoryToken(input: $input) {
    token
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class RegeneratRepositoryTokenTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", active=True)

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "repoName": "gazebo",
                    "owner": "codecov",
                    "tokenType": "PROFILING",
                }
            },
        )
        assert (
            data["regenerateRepositoryToken"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    def test_when_validation_error_repo_not_viewable(self):
        random_user = OwnerFactory(organizations=[self.org.ownerid])
        data = self.gql_request(
            query,
            owner=random_user,
            variables={
                "input": {
                    "repoName": "gazebo",
                    "owner": "codecov",
                    "tokenType": "PROFILING",
                }
            },
        )
        assert (
            data["regenerateRepositoryToken"]["error"]["__typename"]
            == "ValidationError"
        )

    def test_when_authenticated_regenerate_profiling_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )
        RepositoryTokenFactory(repository=self.repo, key="random")
        data = self.gql_request(
            query,
            owner=user,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "gazebo",
                    "tokenType": "PROFILING",
                }
            },
        )
        newToken = data["regenerateRepositoryToken"]["token"]
        assert newToken != "random"
        assert len(newToken) == 40

    def test_when_authenticated_regenerate_staticanalysis_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )
        RepositoryTokenFactory(
            repository=self.repo, key="random", token_type="static_analysis"
        )
        data = self.gql_request(
            query,
            owner=user,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "gazebo",
                    "tokenType": "STATIC_ANALYSIS",
                }
            },
        )
        newToken = data["regenerateRepositoryToken"]["token"]
        assert newToken != "random"
        assert len(newToken) == 40

    def test_when_authenticated_regenerate_upload_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )
        RepositoryTokenFactory(repository=self.repo, key="random", token_type="upload")
        data = self.gql_request(
            query,
            owner=user,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "gazebo",
                    "tokenType": "UPLOAD",
                }
            },
        )
        newToken = data["regenerateRepositoryToken"]["token"]
        assert newToken != "random"
        assert len(newToken) == 40
