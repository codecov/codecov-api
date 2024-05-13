from unittest.mock import patch

from django.test import TransactionTestCase

from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: DeleteComponentMeasurementsInput!) {
        deleteComponentMeasurements(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class DeleteComponentMeasurementsTest(GraphQLTestHelper, TransactionTestCase):
    @patch(
        "core.commands.component.interactors.delete_component_measurements.DeleteComponentMeasurementsInteractor.execute"
    )
    def test_delete_component_measurements(self, execute_mock):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "componentId": "test-component",
                }
            },
        )

        assert data == {"deleteComponentMeasurements": None}

        execute_mock.assert_called_once_with(
            owner_username="test-owner",
            repo_name="test-repo",
            component_id="test-component",
        )

    @patch(
        "core.commands.component.interactors.delete_component_measurements.DeleteComponentMeasurementsInteractor.execute"
    )
    def test_delete_component_measurements_unauthenticated(self, execute_mock):
        execute_mock.side_effect = Unauthenticated()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "componentId": "test-component",
                }
            },
        )

        assert data == {
            "deleteComponentMeasurements": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    @patch(
        "core.commands.component.interactors.delete_component_measurements.DeleteComponentMeasurementsInteractor.execute"
    )
    def test_delete_component_measurements_unauthorized(self, execute_mock):
        execute_mock.side_effect = Unauthorized()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "componentId": "test-component",
                }
            },
        )

        assert data == {
            "deleteComponentMeasurements": {
                "error": {
                    "__typename": "UnauthorizedError",
                    "message": "You are not authorized",
                }
            }
        }

    @patch(
        "core.commands.component.interactors.delete_component_measurements.DeleteComponentMeasurementsInteractor.execute"
    )
    def test_delete_component_measurements_validation_error(self, execute_mock):
        execute_mock.side_effect = ValidationError("test error")

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "componentId": "test-component",
                }
            },
        )

        assert data == {
            "deleteComponentMeasurements": {
                "error": {"__typename": "ValidationError", "message": "test error"}
            }
        }

    @patch(
        "core.commands.component.interactors.delete_component_measurements.DeleteComponentMeasurementsInteractor.execute"
    )
    def test_delete_component_measurements_not_found(self, execute_mock):
        execute_mock.side_effect = NotFound()

        data = self.gql_request(
            query,
            variables={
                "input": {
                    "ownerUsername": "test-owner",
                    "repoName": "test-repo",
                    "componentId": "test-component",
                }
            },
        )

        assert data == {
            "deleteComponentMeasurements": {
                "error": {
                    "__typename": "NotFoundError",
                    "message": "Cant find the requested resource",
                }
            }
        }
