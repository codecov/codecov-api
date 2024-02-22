from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory

from .helper import GraphQLTestHelper


@freeze_time("2023-06-19")
class UserTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(
            username="codecov-user",
            name="codecov-name",
            service="github",
            service_id=1,
            student=True,
            student_created_at=timezone.now(),
            student_updated_at=timezone.now() + timedelta(days=1),
        )

        self.no_subtype_user = OwnerFactory(
            username="codecov-user",
            name="codecov-name",
            service="github",
            service_id=2,
            student=True,
            student_created_at=timezone.now(),
            student_updated_at=timezone.now() + timedelta(days=1),
            user=None,
        )

    def test_query_user_resolver(self):
        query = """
            {
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

    def test_customer_intent_with_no_user_subtype(self):
        query = """
            {
                me {
                    user {
                        customerIntent
                    }
                }
            }
            """
        data = self.gql_request(query, owner=self.no_subtype_user)
        assert data["me"]["user"] == {
            "customerIntent": None,
        }
