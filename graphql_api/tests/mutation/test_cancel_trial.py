from django.test import TransactionTestCase
from prometheus_client import REGISTRY

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper
from graphql_api.views import GQL_HIT_COUNTER, GQL_ERROR_COUNTER, GQL_REQUEST_LATENCIES
from plan.constants import PlanName, TrialStatus

query = """
    mutation($input: CancelTrialInput!) {
        cancelTrial(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class CancelTrialMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None, org_username: str = None):
        return self.gql_request(
            query,
            variables={"input": {"orgUsername": org_username}},
            owner=owner,
        )

    def test_unauthenticated(self):
        assert self._request() == {
            "cancelTrial": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_authenticated(self):
        GQL_HIT_COUNTER.labels(
            operation_type="mutation", operation_name="CancelTrialInput"
        )
        GQL_ERROR_COUNTER.labels(
            operation_type="mutation", operation_name="CancelTrialInput"
        )
        GQL_REQUEST_LATENCIES.labels(
            operation_type="mutation", operation_name="CancelTrialInput"
        )
        before = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        errors_before = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        timer_before = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        trial_status = TrialStatus.ONGOING.value
        owner = OwnerFactory(
            trial_status=trial_status, plan=PlanName.TRIAL_PLAN_NAME.value
        )
        owner.save()
        assert self._request(owner=owner, org_username=owner.username) == {
            "cancelTrial": None
        }
        after = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        errors_after = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        timer_after = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "mutation", "operation_name": "CancelTrialInput"},
        )
        assert after - before == 1
        assert errors_after - errors_before == 0
        assert timer_after - timer_before == 1
