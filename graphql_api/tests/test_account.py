from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    AccountsUsersFactory,
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

    def test_fetch_activated_user_count(self) -> None:
        for _ in range(7):
            AccountsUsersFactory(account=self.account)

        query = """
            query {
                owner(username: "%s") {
                    account {
                        activatedUserCount
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        activatedUserCount = result["owner"]["account"]["activatedUserCount"]
        assert activatedUserCount == 7

    def test_fetch_organizations(self) -> None:
        account = AccountFactory(name="account")
        owner = OwnerFactory(
            username="owner-0",
            plan_activated_users=[],
            account=account,
        )
        OwnerFactory(
            username="owner-1",
            plan_activated_users=[0],
            account=account,
        )
        OwnerFactory(
            username="owner-2",
            plan_activated_users=[0, 1],
            account=account,
        )

        query = """
            query {
                owner(username: "%s") {
                    account {
                        organizations(first: 20) {
                            edges {
                                node {
                                    username
                                    activatedUserCount
                                }
                            }
                        }
                    }
                }
            }
        """ % (owner.username)

        result = self.gql_request(query, owner=owner)

        assert "errors" not in result

        orgs = [
            node["node"]["username"]
            for node in result["owner"]["account"]["organizations"]["edges"]
        ]

        assert orgs == ["owner-0", "owner-1", "owner-2"]

    def test_fetch_organizations_desc(self) -> None:
        account = AccountFactory(name="account")
        owner = OwnerFactory(
            username="owner-0",
            plan_activated_users=[],
            account=account,
        )
        OwnerFactory(
            username="owner-1",
            plan_activated_users=[0],
            account=account,
        )
        OwnerFactory(
            username="owner-2",
            plan_activated_users=[0, 1],
            account=account,
        )

        query = """
            query {
                owner(username: "%s") {
                    account {
                        organizations(first: 20, orderingDirection: DESC) {
                            edges {
                                node {
                                    username
                                    activatedUserCount
                                }
                            }
                        }
                    }
                }
            }
        """ % (owner.username)

        result = self.gql_request(query, owner=owner)

        assert "errors" not in result

        orgs = [
            node["node"]["username"]
            for node in result["owner"]["account"]["organizations"]["edges"]
        ]

        assert orgs == ["owner-2", "owner-1", "owner-0"]

    def test_fetch_organizations_pagination(self) -> None:
        account = AccountFactory(name="account")
        owner = OwnerFactory(
            username="owner-0",
            plan_activated_users=[],
            account=account,
        )
        OwnerFactory(
            username="owner-1",
            plan_activated_users=[0],
            account=account,
        )
        OwnerFactory(
            username="owner-2",
            plan_activated_users=[0, 1],
            account=account,
        )

        query = """
            query {
                owner(username: "%s") {
                    account {
                        organizations(first: 2) {
                            edges {
                                node {
                                    username
                                    activatedUserCount
                                }
                            }
                            totalCount
                            pageInfo {
                                hasNextPage
                            }
                        }
                    }
                }
            }
        """ % (owner.username)

        result = self.gql_request(query, owner=owner)

        assert "errors" not in result

        totalCount = result["owner"]["account"]["organizations"]["totalCount"]

        assert totalCount == 3

        orgs = [
            node["node"]["username"]
            for node in result["owner"]["account"]["organizations"]["edges"]
        ]

        assert orgs == ["owner-0", "owner-1"]

        hasNextPage = result["owner"]["account"]["organizations"]["pageInfo"][
            "hasNextPage"
        ]
        assert hasNextPage
