from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper


class OnboardingTest(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.params = {
            "typeProjects": ["PERSONAL"],
            "goals": ["STARTING_WITH_TESTS", "OTHER"],
            "otherGoal": "feel confident in my code",
        }

    def test_when_not_onboarded(self):
        query = "{ me { onboardingCompleted } }"
        data = self.gql_request(query, owner=self.owner)
        assert data == {"me": {"onboardingCompleted": False}}

    def test_onboarding_mutation(self):
        query = """
        mutation onboarding($input: OnboardUserInput!) {
          onboardUser(input: $input) {
            me {
              onboardingCompleted
              trackingMetadata {
                profile {
                  otherGoal
                  goals
                  typeProjects
                }
              }
            }
          }
        }
        """
        data = self.gql_request(
            query, owner=self.owner, variables={"input": self.params}
        )
        assert data == {
            "onboardUser": {
                "me": {
                    "onboardingCompleted": True,
                    "trackingMetadata": {
                        "profile": {
                            "otherGoal": self.params["otherGoal"],
                            "goals": self.params["goals"],
                            "typeProjects": self.params["typeProjects"],
                        }
                    },
                }
            }
        }
