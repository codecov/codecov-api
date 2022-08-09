import asyncio
import datetime
from unittest.mock import patch

from ariadne import graphql_sync
from django.test import TestCase, override_settings

from .helper import GraphQLTestHelper

query = """{
    loginProviders
}
"""


class TestLoginProvidersType(GraphQLTestHelper, TestCase):
    @override_settings(
        GITHUB_CLIENT_ID="Github",
        GITHUB_ENTERPRISE_CLIENT_ID="Github Enterprise",
        GITLAB_CLIENT_ID="Gitlab",
        GITLAB_ENTERPRISE_CLIENT_ID="Gitlab Enterprise",
        BITBUCKET_CLIENT_ID="Bitbucket",
        BITBUCKET_SERVER_CLIENT_ID="Bitbucket Server",
    )
    def test_fetching_github_providers(self):
        data = self.gql_request(query)
        assert data == {
            "loginProviders": [
                "GITHUB",
                "GITHUB_ENTERPRISE",
                "GITLAB",
                "GITLAB_ENTERPRISE",
                "BITBUCKET",
                "BITBUCKET_SERVER",
            ]
        }
