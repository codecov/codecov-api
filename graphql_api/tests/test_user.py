from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from prometheus_client import REGISTRY
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.types.user.user import resolve_customer_intent

from ..views import GQL_ERROR_COUNTER, GQL_HIT_COUNTER, GQL_REQUEST_LATENCIES
from .helper import GraphQLTestHelper


@freeze_time("2023-06-19")
class UserTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.service_id = 1
        self.user = OwnerFactory(
            username="codecov-user",
            name="codecov-name",
            service="github",
            service_id=self.service_id,
            student=True,
            student_created_at=timezone.now(),
            student_updated_at=timezone.now() + timedelta(days=1),
        )

    def test_query_user_resolver(self):
        GQL_HIT_COUNTER.labels(operation_type="unknown_type", operation_name="me")
        GQL_ERROR_COUNTER.labels(operation_type="unknown_type", operation_name="me")
        GQL_REQUEST_LATENCIES.labels(operation_type="unknown_type", operation_name="me")
        before = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        errors_before = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        timer_before = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        query = """{
            me {
                user {
                    username
                    name
                    avatarUrl
                    student
                    studentCreatedAt
                    studentUpdatedAt
                    customerIntent
                }
            }
        }
        """
        data = self.gql_request(query, owner=self.user)
        assert data["me"]["user"] == {
            "username": "codecov-user",
            "name": "codecov-name",
            "avatarUrl": f"https://avatars0.githubusercontent.com/u/{self.service_id}?v=3&s=55",
            "student": True,
            "studentCreatedAt": "2023-06-19T00:00:00",
            "studentUpdatedAt": "2023-06-20T00:00:00",
            "customerIntent": "Business",
        }
        after = REGISTRY.get_sample_value(
            "api_gql_counts_hits_total",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        errors_after = REGISTRY.get_sample_value(
            "api_gql_counts_errors_total",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        timer_after = REGISTRY.get_sample_value(
            "api_gql_timers_full_runtime_seconds_count",
            labels={"operation_type": "unknown_type", "operation_name": "me"},
        )
        assert after - before == 1
        assert errors_after - errors_before == 0
        assert timer_after - timer_before == 1

    def test_query_null_user_customer_intent_resolver(self):
        null_user = OwnerFactory(user=None, service_id=4)
        data = resolve_customer_intent(null_user, None)
        assert data is None
