import asyncio
from unittest.mock import patch

from ariadne import graphql_sync
from django.test import TestCase, TransactionTestCase, override_settings
from freezegun import freeze_time

from codecov.db import sync_to_async
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import TestFactory

from .helper import GraphQLTestHelper


@freeze_time("2019-01-01T00:00:00")
class TestResultTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="randomOwner")
        self.repository = RepositoryFactory(
            author=self.owner,
        )
        self.test = TestFactory(
            name="Test Name",
            repository=self.repository,
        )

    def test_fetch_test_result_name(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResults {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResults"]["edges"][0]["node"]["name"] == self.test.name


    def test_fetch_test_result_updated_at(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResults {
                                edges {
                                    node {
                                        updatedAt
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResults"]["edges"][0]["node"]["updatedAt"] == "2019-01-01T00:00:00+00:00"


    def test_fetch_test_result_commits_failed(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResults {
                                edges {
                                    node {
                                        commitsFailed
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResults"]["edges"][0]["node"]["commitsFailed"] == self.test.commits_where_fail


    def test_fetch_test_result_failure_rate(self) -> None:
        query = """
            query {
               owner(username: "%s") {
                    repository(name: "%s") {
                        ... on Repository {
                            testResults {
                                edges {
                                    node {
                                        failureRate
                                    }
                                }
                            }
                        }
                    }
                 }
            }
        """ % (self.owner.username, self.repository.name)

        result = self.gql_request(query, owner=self.owner)

        assert "errors" not in result
        assert result["owner"]["repository"]["testResults"]["edges"][0]["node"]["failureRate"] == self.test.failure_rate

