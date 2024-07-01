import asyncio
from unittest.mock import patch
from django.test import TestCase
from ariadne import graphql_sync
from codecov_auth.tests.factories import (
    OwnerFactory,
    AccountFactory,
    OktaSettingsFactory,
)
from .helper import GraphQLTestHelper
from django.test import TransactionTestCase, override_settings
from codecov.db import sync_to_async


class AccountTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.account = AccountFactory(name="Test Account")
        self.owner = OwnerFactory(
            username="randomOwner", service="github", account=self.account
        )
        self.okta_settings = OktaSettingsFactory(
            account=self.account,
            client_id="test-client-id",
            client_secret="test-client-secret",
        )

    def test_fetch_okta_config(self):
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
