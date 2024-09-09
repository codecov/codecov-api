import datetime

from django.test import TransactionTestCase
from django.utils import timezone

from codecov_auth.tests.factories import OwnerFactory
from core.models import Repository
from core.tests.factories import (
    CommitFactory,
    RepositoryFactory,
)

from .helper import GraphQLTestHelper

query_coverage_analytics_base_fields = """
query CoverageAnalytics($owner:String!, $repo: String!) {
    owner(username:$owner) {
      repository(name: $repo) {
        __typename
        ... on Repository {
          name
          coverageAnalytics {
            %s
          }
        }
        ... on ResolverError {
          message
        }
      }
    }
}
"""

default_coverage_analytics_base_fields = """
    percentCovered
    commitSha
    hits
    misses
    lines
"""


class TestFetchCoverageAnalyticsBaseFields(GraphQLTestHelper, TransactionTestCase):
    def fetch_coverage_analytics(
        self, repo_name, fields=None
    ):
        query = query_coverage_analytics_base_fields % (fields or default_coverage_analytics_base_fields)
        variables = {"owner": "codecov-user", "repo": repo_name}
        return self.gql_request(query=query, owner=self.owner, variables=variables)

    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.yaml = {"test": "test"}

    def test_coverage_analytics_base_fields(self):
        # Create repo, commit, and coverage data
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            name="b",
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )
        hour_ago = timezone.make_aware(datetime.datetime(2020, 12, 31, 23, 0))
        coverage_commit = CommitFactory(
            repository=repo,
            totals={"c": 75, "h": 30, "m": 10, "n": 40},
            timestamp=hour_ago,
        )
        CommitFactory(repository=repo, totals={"c": 85})

        # Update the timestamp and save to db
        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(
            repo.pk, "Repository should be saved and have a primary key."
        )

        # Query the db using the repository model
        repo_from_db = Repository.objects.get(pk=repo.pk)
        self.assertIsNotNone(repo_from_db.updatestamp)

        # Fetch the coverage analytics data
        coverage_analytics_data = self.fetch_coverage_analytics(repo.name)

        # Define the expected response
        expected_response = {
            "__typename": "Repository",
            "name": repo.name,
            "coverageAnalytics": {
                "percentCovered": 75,
                "commitSha": coverage_commit.commitid,
                "hits": 30,
                "misses": 10,
                "lines": 40,
            },
        }

        # Compare the actual data with the expected data
        assert coverage_analytics_data["owner"]["repository"] == expected_response

    def test_coverage_analytics_base_fields_partial(self):
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            name="b",
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )
        hour_ago = timezone.make_aware(datetime.datetime(2020, 12, 31, 23, 0))
        CommitFactory(repository=repo, totals={"c": 75, "h": 30, "m": 10, "n": 40}, timestamp=hour_ago)
        repo.updatestamp = timezone.now()
        repo.save()

        fields = "percentCovered"
        coverage_data = self.fetch_coverage_analytics(repo.name, fields=fields)
        print(coverage_data)
        assert coverage_data["owner"]["repository"]["coverageAnalytics"]["percentCovered"] == 75

    def test_coverage_analytics_no_commit(self):
        """Test case where no commits exist for coverage data"""
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            name="empty-repo",
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )
        repo.save()

        coverage_data = self.fetch_coverage_analytics(repo.name)
        assert coverage_data["owner"]["repository"]["coverageAnalytics"] == {
            "percentCovered": None,
            "commitSha": None,
            "hits": None,
            "misses": None,
            "lines": None,
        }
