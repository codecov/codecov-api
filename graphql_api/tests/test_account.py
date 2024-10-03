from django.test import TransactionTestCase

from codecov_auth.tests.factories import (
    AccountFactory,
    OktaSettingsFactory,
    OwnerFactory,
)

from .helper import GraphQLTestHelper


class AccountTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.account = AccountFactory(
            name="Test Account", plan_seat_count=10, free_seat_count=1
        )
        self.owner = OwnerFactory(
            username="randomOwner", service="github", account=self.account
        )
        self.okta_settings = OktaSettingsFactory(
            account=self.account,
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    def test_fetch_okta_config(self) -> None:
        query = """
            query {
                owner(username: "%s"){
                    account {
                        oktaConfig {
                            clientId
                            clientSecret
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        data = result["owner"]["account"]
        assert data["oktaConfig"]["clientId"] == "test-client-id"
        assert data["oktaConfig"]["clientSecret"] == "test-client-secret"

    def test_fetch_total_seat_count(self) -> None:
        query = """
            query {
                owner(username: "%s"){
                    account {
                        totalSeatCount
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        seatCount = result["owner"]["account"]["totalSeatCount"]
        assert seatCount == 11
