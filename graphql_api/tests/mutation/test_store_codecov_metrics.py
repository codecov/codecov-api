from django.test import TransactionTestCase
from shared.django_apps.codecov_metrics.models import UserOnboardingLifeCycleMetrics
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: StoreEventMetricsInput!) {
        storeEventMetric(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class StoreEventMetricMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, org_username: str, event: str, json_payload: str, owner=None):
        return self.gql_request(
            query,
            variables={
                "input": {
                    "orgUsername": org_username,
                    "eventName": event,
                    "jsonPayload": json_payload,
                }
            },
            owner=owner,
        )

    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_unauthenticated(self):
        response = self._request(
            org_username="codecov-user",
            event="VISITED_PAGE",
            json_payload='{"key": "value"}',
        )
        assert response == {
            "storeEventMetric": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_authenticated_inserts_into_db(self):
        self._request(
            org_username="codecov-user",
            event="VISITED_PAGE",
            json_payload='{"some-key": "some-value"}',
            owner=self.owner,
        )
        metric = UserOnboardingLifeCycleMetrics.objects.filter(
            event="VISITED_PAGE"
        ).first()
        self.assertIsNotNone(metric)
        self.assertEqual(metric.additional_data, {"some-key": "some-value"})

    def test_invalid_org(self):
        response = self._request(
            org_username="invalid_org",
            event="VISITED_PAGE",
            json_payload='{"key": "value"}',
            owner=self.owner,
        )
        assert response == {
            "storeEventMetric": {
                "error": {
                    "__typename": "ValidationError",
                    "message": "Cannot find owner record in the database",
                }
            }
        }

    def test_invalid_event(self):
        self._request(
            org_username="codecov-user",
            event="INVALID_EVENT",
            json_payload='{"key": "value"}',
            owner=self.owner,
        )
        metric = UserOnboardingLifeCycleMetrics.objects.filter(
            event="INVALID_EVENT"
        ).first()
        self.assertIsNone(metric)

    def test_invalid_json_string(self):
        response = self._request(
            org_username="codecov-user",
            event="VISITED_PAGE",
            json_payload="invalid-json",
            owner=self.owner,
        )
        assert response == {
            "storeEventMetric": {
                "error": {
                    "__typename": "ValidationError",
                    "message": "Invalid JSON string",
                }
            }
        }
