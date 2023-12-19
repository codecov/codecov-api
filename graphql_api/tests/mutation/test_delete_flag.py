from unittest.mock import patch

from django.test import TransactionTestCase, override_settings

from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: DeleteFlagInput!) {
        deleteFlag(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class DeleteFlagTest(GraphQLTestHelper, TransactionTestCase):
    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag(self, execute_mock):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {"deleteFlag": None}

        assert execute_mock.called_once_with(
            owner_username="test-owner",
            repo_name="test-repo",
            flag_name="test-flag",
        )

    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_unauthenticated(self, execute_mock):
        execute_mock.side_effect = Unauthenticated()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {
            "deleteFlag": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_unauthorized(self, execute_mock):
        execute_mock.side_effect = Unauthorized()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {
            "deleteFlag": {
                "error": {
                    "__typename": "UnauthorizedError",
                    "message": "You are not authorized",
                }
            }
        }

    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_validation_error(self, execute_mock):
        execute_mock.side_effect = ValidationError("test error")

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {
            "deleteFlag": {
                "error": {"__typename": "ValidationError", "message": "test error"}
            }
        }

    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_not_found(self, execute_mock):
        execute_mock.side_effect = NotFound()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {
            "deleteFlag": {
                "error": {
                    "__typename": "NotFoundError",
                    "message": "Cant find the requested resource",
                }
            }
        }

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.get_config")
    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_self_hosted_admin(self, execute_mock, get_config_mock):
        get_config_mock.return_value = [
            {"service": "github", "username": "test-owner"},
        ]

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {"deleteFlag": None}

        assert execute_mock.called_once_with(
            owner_username="test-owner",
            repo_name="test-repo",
            flag_name="test-flag",
        )

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.get_config")
    @patch("core.commands.flag.interactors.delete_flag.DeleteFlagInteractor.execute")
    def test_delete_flag_self_hosted_not_admin(self, execute_mock, get_config_mock):
        execute_mock.side_effect = Unauthorized()
        get_config_mock.return_value = [
            {"service": "github", "username": "someone-else"},
        ]

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "flagName": "test-flag",
                }
            },
        )

        assert data == {
            "deleteFlag": {
                "error": {
                    "__typename": "UnauthorizedError",
                    "message": "You are not authorized",
                }
            }
        }
