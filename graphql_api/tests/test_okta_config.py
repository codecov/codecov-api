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


class OktaConfigTestCase(GraphQLTestHelper, TransactionTestCase):
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

    def test_fetch_enabled_okta_config(self):
        query = """
            query {
                owner(username: "%s"){
                    account {
                        oktaConfig {
                            enabled
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"]["enabled"] == True

    def test_fetch_disabled_okta_config(self):
        self.okta_settings.enabled = False
        self.okta_settings.save()
        query = """
            query {
                owner(username: "%s"){
                    account {
                        oktaConfig {
                            enabled
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"]["enabled"] == False

    def test_fetch_enforced_okta_config(self):
        query = """
            query {
                owner(username: "%s"){
                    account {
                        oktaConfig {
                            enforced
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"]["enforced"] == False

    def test_fetch_enforced_okta_config_true(self):
        self.okta_settings.enforced = True
        self.okta_settings.save()
        query = """
            query {
                owner(username: "%s"){
                    account {
                        oktaConfig {
                            enforced
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"]["enforced"] == True

    def test_fetch_url_okta_config(self):
        query = """
            query {
                owner(username: "%s"){
                    account{
                        oktaConfig {
                            url
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"]["url"] == self.okta_settings.url

    def test_fetch_okta_config_client_id(self):
        query = """
            query {
                owner(username: "%s"){
                    account{
                        oktaConfig {
                            clientId
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["account"]["oktaConfig"]["clientId"]
            == self.okta_settings.client_id
        )

    def test_fetch_okta_config_client_secret(self):
        query = """
            query {
                owner(username: "%s"){
                    account{
                        oktaConfig {
                            clientSecret
                        }
                    }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert (
            result["owner"]["account"]["oktaConfig"]["clientSecret"]
            == self.okta_settings.client_secret
        )

    def test_fetch_non_existent_okta_config(self):
        self.okta_settings.delete()

        query = """
            query {
                owner(username: "%s"){
                account{
                    oktaConfig {
                        clientId
                        clientSecret
                        url
                    }
                }
                }
            }
        """ % (self.owner.username)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["account"]["oktaConfig"] is None
