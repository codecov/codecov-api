from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.types.user.user import resolve_customer_intent

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

    def test_query_null_user_customer_intent_resolver(self):
        null_user = OwnerFactory(user=None, service_id=4)
        data = resolve_customer_intent(null_user, None)
        assert data == None
