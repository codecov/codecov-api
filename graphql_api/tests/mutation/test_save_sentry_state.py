from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper
from services.sentry import SentryInvalidStateError, SentryUserAlreadyExistsError

query = """
    mutation($input: SaveSentryStateInput!) {
        saveSentryState(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


@patch("services.sentry.save_sentry_state")
class SaveSentryStateMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None):
        return self.gql_request(
            query,
            variables={"input": {"state": "test-state"}},
            owner=owner,
        )

    def test_unauthenticated(self, save_sentry_state):
        assert self._request() == {
            "saveSentryState": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_invalid_state(self, save_sentry_state):
        save_sentry_state.side_effect = SentryInvalidStateError()
        assert self._request(owner=OwnerFactory()) == {
            "saveSentryState": {
                "error": {
                    "__typename": "ValidationError",
                    "message": "Invalid state",
                }
            }
        }

    def test_sentry_user_already_exists(self, save_sentry_state):
        save_sentry_state.side_effect = SentryUserAlreadyExistsError()
        assert self._request(owner=OwnerFactory()) == {
            "saveSentryState": {
                "error": {
                    "__typename": "ValidationError",
                    "message": "Invalid Sentry user",
                }
            }
        }

    def test_authenticated(self, save_sentry_state):
        owner = OwnerFactory()
        assert self._request(owner=owner) == {"saveSentryState": None}

        save_sentry_state.assert_called_once_with(owner, "test-state")
