from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: ActivateMeasurementsInput!) {
  activateMeasurements(input: $input) {
    error {
      __typename
    }
  }
}
"""


query = """
mutation UpdateBundleCacheConfig(
    $owner: String!
    $repoName: String!
    $bundles: [BundleCacheConfigInput!]!
) {
    updateBundleCacheConfig(input: {
        owner: $owner,
        repoName: $repoName,
        bundles: $bundles
    }) {
        results {
            bundleName
            isCached
            cacheConfig
        }
        error {
            __typename
            ... on UnauthenticatedError {
                message
            }
            ... on ValidationError {
                message
            }
        }
    }
}
"""


class UpdateBundleCacheConfigTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory()

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "owner": "codecov",
                "repoName": "test-repo",
                "bundles": [{"bundleName": "pr_bundle1", "toggleCaching": True}],
            },
        )
        assert (
            data["updateBundleCacheConfig"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    @patch(
        "core.commands.repository.interactors.update_bundle_cache_config.UpdateBundleCacheConfigInteractor.execute"
    )
    def test_when_authenticated(self, execute):
        data = self.gql_request(
            query,
            owner=self.owner,
            variables={
                "owner": "codecov",
                "repoName": "test-repo",
                "bundles": [{"bundleName": "pr_bundle1", "toggleCaching": True}],
            },
        )
        assert data == {"updateBundleCacheConfig": {"results": [], "error": None}}
