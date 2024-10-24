from django.test import TransactionTestCase, override_settings
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: UpdateSelfHostedSettingsInput!) {
        updateSelfHostedSettings(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class UpdateSelfHostedSettingsTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None):
        return self.gql_request(
            query,
            variables={"input": {"shouldAutoActivate": True}},
            owner=owner,
        )

    def _request_deactivate(self, owner=None):
        return self.gql_request(
            query,
            variables={"input": {"shouldAutoActivate": False}},
            owner=owner,
        )

    @override_settings(IS_ENTERPRISE=True)
    def test_unauthenticated(self):
        assert self._request() == {
            "updateSelfHostedSettings": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    @override_settings(IS_ENTERPRISE=True)
    def test_authenticated_enable_autoactivation(self):
        owner = OwnerFactory()
        assert self._request(owner=owner) == {"updateSelfHostedSettings": None}

    @override_settings(IS_ENTERPRISE=True)
    def test_authenticate_disable_autoactivation(self):
        owner = OwnerFactory()
        assert self._request_deactivate(owner=owner) == {
            "updateSelfHostedSettings": None
        }

    @override_settings(IS_ENTERPRISE=False)
    def test_invalid_settings(self):
        owner = OwnerFactory()
        assert self._request(owner=owner) == {
            "updateSelfHostedSettings": {
                "error": {
                    "__typename": "ValidationError",
                    "message": "enable_autoactivation and disable_autoactivation are only available in self-hosted environments",
                }
            }
        }
