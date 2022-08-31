from unittest.mock import patch

from django.test import TestCase, override_settings

from .helper import GraphQLTestHelper


class TestConfigType(GraphQLTestHelper, TestCase):
    @override_settings(
        GITHUB_CLIENT_ID="Github",
        GITHUB_ENTERPRISE_CLIENT_ID="Github Enterprise",
        GITLAB_CLIENT_ID="Gitlab",
        GITLAB_ENTERPRISE_CLIENT_ID="Gitlab Enterprise",
        BITBUCKET_CLIENT_ID="Bitbucket",
        BITBUCKET_SERVER_CLIENT_ID="Bitbucket Server",
    )
    def test_login_providers(self):
        data = self.gql_request("query { config { loginProviders }}")
        assert data == {
            "config": {
                "loginProviders": [
                    "GITHUB",
                    "GITHUB_ENTERPRISE",
                    "GITLAB",
                    "GITLAB_ENTERPRISE",
                    "BITBUCKET",
                    "BITBUCKET_SERVER",
                ],
            },
        }

    def test_seats_used(self):
        data = self.gql_request("query { config { seatsUsed }}")
        assert data == {
            "config": {
                "seatsUsed": None,
            },
        }

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.activated_owners")
    def test_seats_used_self_hosted(self, activated_owners):
        activated_owners.count.return_value = 1
        data = self.gql_request("query { config { seatsUsed }}")
        assert data == {
            "config": {
                "seatsUsed": 1,
            },
        }

    def test_seats_limit(self):
        data = self.gql_request("query { config { seatsLimit }}")
        assert data == {
            "config": {
                "seatsLimit": None,
            },
        }

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.license_seats")
    def test_seats_limit_self_hosted(self, license_seats):
        license_seats.return_value = 123
        data = self.gql_request("query { config { seatsLimit }}")
        assert data == {
            "config": {
                "seatsLimit": 123,
            },
        }
