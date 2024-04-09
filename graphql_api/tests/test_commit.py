import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

import yaml
from django.test import TransactionTestCase
from shared.bundle_analysis import StoragePaths
from shared.bundle_analysis.storage import get_bucket_name
from shared.reports.types import LineSession
from shared.storage.memory import MemoryStorageService

import services.comparison as comparison
from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitErrorFactory, CommitFactory, RepositoryFactory
from graphql_api.types.enums import UploadErrorEnum, UploadState
from graphql_api.types.enums.enums import UploadType
from reports.models import CommitReport
from reports.tests.factories import (
    CommitReportFactory,
    ReportLevelTotalsFactory,
    RepositoryFlagFactory,
    UploadErrorFactory,
    UploadFactory,
    UploadFlagMembershipFactory,
)
from services.archive import ArchiveService
from services.comparison import MissingComparisonReport
from services.components import Component
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper, paginate_connection

query_commit = """
query FetchCommit($org: String!, $repo: String!, $commit: String!) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                commit(id: $commit) {
                    %s
                }
            }
        }
    }
}
"""

query_commits = """
query FetchCommits($org: String!, $repo: String!) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                commits {
                    edges {
                        node {
                            %s
                        }
                    }
                }
            }
        }
    }
}
"""


class MockCoverage(object):
    def __init__(self, cov):
        self.coverage = cov
        self.sessions = [
            LineSession(0, None),
            LineSession(1, None),
            LineSession(2, None),
        ]


class MockLines(object):
    def __init__(self):
        self.lines = [
            [0, MockCoverage("1/2")],
            [1, MockCoverage(1)],
            [2, MockCoverage(0)],
        ]
        self.totals = MockCoverage(83)


class MockReport(object):
    def get(self, file, _else):
        lines = MockLines()
        return MockLines()

    def filter(self, **kwargs):
        return self

    @property
    def flags(self):
        return {"flag_a": True, "flag_b": True}


class EmptyReport(MockReport):
    def get(self, file, _else):
        return None


class TestCommit(GraphQLTestHelper, TransactionTestCase):
    pass
