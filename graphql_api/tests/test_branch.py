from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.reports.types import ReportTotals

from services.components import Component
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

query_branch = """
    query FetchBranch($org: String!, $repo: String!, $branch: String!) {
        owner(username: $org) {
            repository(name: $repo) {
                ... on Repository {
                    branch(name: $branch) {
                        %s
                    }
                }
            }
        }
    }
"""

query_files = """
    query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!) {
        owner(username: $org) {
            repository(name: $repo) {
                ... on Repository {
                    branch(name: $branch) {
                        head {
                            pathContents (path: $path, filters: $filters) {
                                __typename
                                ... on PathContents {
                                    results {
                                        __typename
                                        name
                                        path
                                        hits
                                        misses
                                        partials
                                        lines
                                        percentCovered
                                        ... on PathContentFile {
                                            isCriticalFile
                                        }
                                    }
                                }
                                ... on MissingHeadReport {
                                    message
                                }
                                ... on MissingCoverage {
                                    message
                                }
                                ... on UnknownPath {
                                    message
                                }
                                ... on UnknownFlags {
                                    message
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""

query_files_connection = """
    query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!, $first: Int, $after: String, $last: Int, $before: String) {
        owner(username: $org) {
            repository(name: $repo) {
                ... on Repository {
                    branch(name: $branch) {
                        head {
                            deprecatedPathContents (path: $path, filters: $filters, first: $first, after: $after, last: $last, before: $before) {
                                __typename
                                ... on PathContentConnection {
                                    edges {
                                        cursor
                                        node {
                                            __typename
                                            name
                                            path
                                            hits
                                            misses
                                            partials
                                            lines
                                            percentCovered
                                            ... on PathContentFile {
                                                isCriticalFile
                                            }
                                        }
                                    }
                                    totalCount
                                    pageInfo {
                                        hasNextPage
                                        hasPreviousPage
                                        startCursor
                                        endCursor
                                    }
                                }
                                ... on MissingHeadReport {
                                    message
                                }
                                ... on MissingCoverage {
                                    message
                                }
                                ... on UnknownPath {
                                    message
                                }
                                ... on UnknownFlags {
                                    message
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""


class MockCoverage(object):
    def __init__(self, coverage, hits, lines):
        self.coverage = coverage
        self.hits = hits
        self.lines = lines


class MockTotals(object):
    def __init__(self):
        self.totals = ReportTotals.default_totals()
        self.totals.hits = 8
        self.totals.lines = 10


class MockFlag(object):
    @property
    def totals(self):
        return MockTotals()


class MockSession(object):
    pass


class MockFile:
    def __init__(self, name: str):
        self.name = name


class MockReport(object):
    def __init__(self):
        self.sessions = {1: MockSession()}

    def get(self, file):
        return MockTotals()

    @property
    def files(self):
        return [
            "fileA.py",
            "fileB.py",
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]

    def __iter__(self):
        for name in self.files:
            yield MockFile(name)

    @property
    def flags(self):
        return {"flag-a": MockFlag()}

    def get_file_totals(self, path):
        return MockTotals().totals

    def filter(self, paths, flags):
        return MockFilteredReport()

    def sessions(self):
        return [1, 2, 3]


class MockFilteredReport(MockReport):
    pass


class MockNoFlagsReport(object):
    def __init__(self):
        self.sessions = {1: MockSession()}

    @property
    def flags(self):
        return None


class TestBranch(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.head = CommitFactory(repository=self.repo, timestamp=datetime.now())
        self.commit = CommitFactory(repository=self.repo)
        self.branch = BranchFactory(
            repository=self.repo,
            head=self.head.commitid,
            name="test1",
            updatestamp=(datetime.now() + timedelta(1)),
        )
        self.branch_2 = BranchFactory(
            repository=self.repo,
            head=self.commit.commitid,
            name="test2",
            updatestamp=(datetime.now() + timedelta(2)),
        )

    def test_fetch_branch(self):
        query = query_branch % "name, headSha, head { commitid }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["branch"] == {
            "name": self.branch.name,
            "headSha": self.head.commitid,
            "head": {
                "commitid": self.head.commitid,
            },
        }

    def test_fetch_branch_missing_commit(self):
        self.head.delete()
        query = query_branch % "name, headSha, head { commitid }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["branch"] == {
            "name": self.branch.name,
            "headSha": self.branch.head,
            "head": None,
        }

    def test_fetch_branches(self):
        query_branches = """{
            owner(username: "%s") {
                repository(name: "%s") {
                    ... on Repository {
                        branches {
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
        """
        variables = {"org": self.org.username, "repo": self.repo.name}
        query = query_branches % (self.org.username, self.repo.name)
        data = self.gql_request(query, variables=variables)
        branches = data["owner"]["repository"]["branches"]["edges"]
        assert isinstance(branches, list)
        assert len(branches) == 3
        assert branches == [
            {"node": {"name": "test2"}},
            {"node": {"name": "test1"}},
            {"node": {"name": "main"}},
        ]

    def test_fetch_branches_with_filters(self):
        query_branches = """{
            owner(username: "%s") {
                repository(name: "%s") {
                    ... on Repository {
                        branches (filters: {searchValue: "%s"}) {
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
        """
        variables = {"org": self.org.username, "repo": self.repo.name}
        query = query_branches % (self.org.username, self.repo.name, "test2")
        data = self.gql_request(query, variables=variables)
        branches = data["owner"]["repository"]["branches"]["edges"]
        assert isinstance(branches, list)
        assert len(branches) == 1
        assert branches == [
            {"node": {"name": "test2"}},
        ]

    @override_settings(DEBUG=True)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_with_no_report(self, report_mock):
        report_mock.return_value = None
        commit_without_report = CommitFactory(repository=self.repo)
        branch = BranchFactory(
            repository=self.repo,
            head=commit_without_report.commitid,
            name="branch-two",
            updatestamp=(datetime.now() + timedelta(1)),
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": branch.name,
            "path": "",
            "filters": {},
        }
        data = self.gql_request(query_files, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "MissingHeadReport",
                                "message": "Missing head report",
                            }
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_with_files(self, report_mock, critical_files):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "ordering": {
                    "direction": "DESC",
                    "parameter": "NAME",
                }
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("fileA.py")]

        data = self.gql_request(query_files, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentDir",
                                        "name": "folder",
                                        "path": "folder",
                                        "hits": 24,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 30,
                                        "percentCovered": 80.0,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileA.py",
                                        "path": "fileA.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": True,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_path_prefix(
        self, report_mock, critical_files
    ):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "folder",
            "filters": {
                "ordering": {
                    "direction": "ASC",
                    "parameter": "HITS",
                }
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("folder/fileB.py")]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "folder/fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": True,
                                    },
                                    {
                                        "__typename": "PathContentDir",
                                        "name": "subfolder",
                                        "path": "folder/subfolder",
                                        "hits": 16,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 20,
                                        "percentCovered": 80.0,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_search_value_case_insensitive(
        self, report_mock, critical_files
    ):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "searchValue": "fileB",
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("folder/fileB.py")]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "folder/fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": True,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_list_display_type(self, report_mock):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "displayType": "LIST",
            },
        }
        report_mock.return_value = MockReport()

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileA.py",
                                        "path": "fileA.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "folder/fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileC.py",
                                        "path": "folder/subfolder/fileC.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileD.py",
                                        "path": "folder/subfolder/fileD.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }
        assert len(
            data["owner"]["repository"]["branch"]["head"]["pathContents"]["results"]
        ) == len(report_mock.return_value.files)

    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_missing_coverage(
        self, report_mock, paths_mock, provider_path_exists_mock
    ):
        report_mock.return_value = MockReport()
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = True

        data = self.gql_request(
            query_files,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "invalid",
                "filters": {},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "MissingCoverage",
                                "message": "missing coverage for path: invalid",
                            }
                        }
                    }
                }
            }
        }

    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_unknown_path(
        self, report_mock, paths_mock, provider_path_exists_mock
    ):
        report_mock.return_value = MockReport()
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = False

        data = self.gql_request(
            query_files,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "invalid",
                "filters": {},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "UnknownPath",
                                "message": "path does not exist: invalid",
                            }
                        }
                    }
                }
            }
        }

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_unknown_flags_no_flags(self, report_mock):
        report_mock.return_value = MockNoFlagsReport()

        data = self.gql_request(
            query_files,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "",
                "filters": {"flags": ["test-123"]},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "UnknownFlags",
                                "message": "No coverage with chosen flags: ['test-123']",
                            }
                        }
                    }
                }
            }
        }

    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_component_filter_missing_coverage(
        self, report_mock, commit_components_mock
    ):
        components = ["ComponentThree"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components},
        }

        report_mock.return_value = MockReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "c1",
                    "name": "ComponentOne",
                    "paths": ["fileA.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "c2",
                    "name": "ComponentTwo",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                }
            ),
        ]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "MissingCoverage",
                                "message": f"missing coverage for report with components: {components}",
                            }
                        }
                    }
                }
            }
        }

    @patch("services.components.component_filtered_report")
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_component_filter_has_coverage(
        self, report_mock, commit_components_mock, filtered_mock
    ):
        components = ["Global"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components},
        }

        report_mock.return_value = MockReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "c1",
                    "name": "ComponentOne",
                    "paths": ["fileA.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "c2",
                    "name": "ComponentTwo",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                }
            ),
        ]
        filtered_mock.return_value = MockReport()

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentDir",
                                        "hits": 24,
                                        "lines": 30,
                                        "misses": 0,
                                        "name": "folder",
                                        "partials": 0,
                                        "path": "folder",
                                        "percentCovered": 80.0,
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch("services.components.component_filtered_report")
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.report.files_belonging_to_flags")
    @patch("services.report.files_in_sessions")
    def test_fetch_path_contents_component_and_flag_filters(
        self,
        session_files_mock,
        flag_files_mock,
        report_mock,
        commit_components_mock,
        filtered_mock,
    ):
        session_files_mock.return_value = ["fileA.py"]
        flag_files_mock.return_value = ["fileA.py"]
        report_mock.return_value = MockReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "unit",
                    "name": "unit",
                    "paths": ["fileA.py"],
                    "flag_regexes": "flag-a",
                }
            ),
            Component.from_dict(
                {
                    "component_id": "integration",
                    "name": "integration",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                    "flag_regexes": "flag-a",
                }
            ),
        ]
        filtered_mock.return_value = MockReport()

        query_files = """
            query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            branch(name: $branch) {
                                head {
                                    pathContents (path: $path, filters: $filters) {
                                        __typename
                                        ... on PathContents {
                                            results {
                                                __typename
                                                name
                                                path
                                            }
                                        }
                                        ... on MissingCoverage {
                                            message
                                        }
                                        ... on UnknownFlags {
                                            message
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        components, flags = ["unit"], ["flag-a"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components, "flags": flags},
        }
        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileA.py",
                                        "path": "fileA.py",
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch("services.components.component_filtered_report")
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.report.files_belonging_to_flags")
    def test_fetch_path_contents_component_and_flag_filters_unknown_flags(
        self, flag_files_mock, report_mock, commit_components_mock, filtered_mock
    ):
        flag_files_mock.return_value = ["fileA.py"]
        report_mock.return_value = MockNoFlagsReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "unit",
                    "name": "unit",
                    "paths": ["fileA.py"],
                    "flag_regexes": "flag-a",
                }
            ),
            Component.from_dict(
                {
                    "component_id": "integration",
                    "name": "integration",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                    "flag_regexes": "flag-a",
                }
            ),
        ]
        filtered_mock.return_value = MockNoFlagsReport()

        query_files = """
            query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            branch(name: $branch) {
                                head {
                                    pathContents (path: $path, filters: $filters) {
                                        __typename
                                        ... on PathContents {
                                            results {
                                                __typename
                                                name
                                                path
                                            }
                                        }
                                        ... on MissingCoverage {
                                            message
                                        }
                                        ... on UnknownFlags {
                                            message
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        components, flags = ["integration"], ["flag-a"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components, "flags": flags},
        }
        data = self.gql_request(query_files, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "UnknownFlags",
                                "message": f"No coverage with chosen flags: {flags}",
                            }
                        }
                    }
                }
            }
        }

    @patch("services.components.component_filtered_report")
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.report.files_belonging_to_flags")
    @patch("services.report.files_in_sessions")
    def test_fetch_path_contents_component_flags_filters(
        self,
        session_files_mock,
        flag_files_mock,
        report_mock,
        commit_components_mock,
        filtered_mock,
    ):
        session_files_mock.return_value = ["fileA.py"]
        flag_files_mock.return_value = ["fileA.py"]
        report_mock.return_value = MockReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "unit",
                    "name": "unit",
                    "paths": ["fileA.py"],
                    "flag_regexes": "flag-a",
                }
            ),
            Component.from_dict(
                {
                    "component_id": "integration",
                    "name": "integration",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                    "flag_regexes": "flag-a",
                }
            ),
        ]
        filtered_mock.return_value = MockReport()

        query_files = """
            query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            branch(name: $branch) {
                                head {
                                    pathContents (path: $path, filters: $filters) {
                                        __typename
                                        ... on PathContents {
                                            results {
                                                __typename
                                                name
                                                path
                                            }
                                        }
                                        ... on MissingCoverage {
                                            message
                                        }
                                        ... on UnknownFlags {
                                            message
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        components = ["unit"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components},
        }
        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileA.py",
                                        "path": "fileA.py",
                                    }
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated(self, report_mock, critical_files_mock):
        report_mock.return_value = MockReport()
        critical_files_mock.return_value = []

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {},
        }

        data = self.gql_request(query_files, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": {
                                "__typename": "PathContents",
                                "results": [
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileA.py",
                                        "path": "fileA.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentFile",
                                        "name": "fileB.py",
                                        "path": "fileB.py",
                                        "hits": 8,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 10,
                                        "percentCovered": 80.0,
                                        "isCriticalFile": False,
                                    },
                                    {
                                        "__typename": "PathContentDir",
                                        "name": "folder",
                                        "path": "folder",
                                        "hits": 24,
                                        "misses": 0,
                                        "partials": 0,
                                        "lines": 30,
                                        "percentCovered": 80.0,
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_paginated(
        self, report_mock, critical_files_mock
    ):
        report_mock.return_value = MockReport()
        critical_files_mock.return_value = []

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {},
            "first": 2,
        }

        data = self.gql_request(query_files_connection, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "PathContentConnection",
                                "edges": [
                                    {
                                        "cursor": "0",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileA.py",
                                            "path": "fileA.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                    {
                                        "cursor": "1",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileB.py",
                                            "path": "fileB.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                ],
                                "totalCount": 3,
                                "pageInfo": {
                                    "hasNextPage": True,
                                    "hasPreviousPage": False,
                                    "startCursor": "0",
                                    "endCursor": "1",
                                },
                            }
                        }
                    }
                }
            }
        }

    @override_settings(DEBUG=True)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_with_no_report(self, report_mock):
        report_mock.return_value = None
        commit_without_report = CommitFactory(repository=self.repo)
        branch = BranchFactory(
            repository=self.repo,
            head=commit_without_report.commitid,
            name="branch-two",
            updatestamp=(datetime.now() + timedelta(1)),
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": branch.name,
            "path": "",
            "filters": {},
        }
        data = self.gql_request(query_files_connection, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "MissingHeadReport",
                                "message": "Missing head report",
                            }
                        }
                    }
                }
            }
        }

    @override_settings(DEBUG=True)
    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_missing_coverage(
        self, report_mock, paths_mock, provider_path_exists_mock
    ):
        report_mock.return_value = MockReport()
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = True

        data = self.gql_request(
            query_files_connection,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "invalid",
                "filters": {},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "MissingCoverage",
                                "message": "missing coverage for path: invalid",
                            }
                        }
                    }
                }
            }
        }

    @override_settings(DEBUG=True)
    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_unknown_path(
        self, report_mock, paths_mock, provider_path_exists_mock
    ):
        report_mock.return_value = MockReport()
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = False

        data = self.gql_request(
            query_files_connection,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "invalid",
                "filters": {},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "UnknownPath",
                                "message": "path does not exist: invalid",
                            }
                        }
                    }
                }
            }
        }

    @override_settings(DEBUG=True)
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_unknown_flags_no_flags(self, report_mock):
        report_mock.return_value = MockNoFlagsReport()

        data = self.gql_request(
            query_files_connection,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "branch": self.branch.name,
                "path": "",
                "filters": {"flags": ["test-123"]},
            },
        )
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "UnknownFlags",
                                "message": "No coverage with chosen flags: ['test-123']",
                            }
                        }
                    }
                }
            }
        }

    @override_settings(DEBUG=True)
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_component_filter_missing_coverage(
        self, report_mock, commit_components_mock
    ):
        components = ["ComponentThree"]
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {"components": components},
        }

        report_mock.return_value = MockReport()
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "c1",
                    "name": "ComponentOne",
                    "paths": ["fileA.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "c2",
                    "name": "ComponentTwo",
                    "paths": ["fileB.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": ["(?s:.*/[^\\/]*\\.py.*)\\Z"],
                }
            ),
        ]

        data = self.gql_request(query_files_connection, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "MissingCoverage",
                                "message": f"missing coverage for report with components: {components}",
                            }
                        }
                    }
                }
            }
        }

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_path_contents_deprecated_with_files_and_list_display_type(
        self, report_mock
    ):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "displayType": "LIST",
            },
        }
        report_mock.return_value = MockReport()

        data = self.gql_request(query_files_connection, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "deprecatedPathContents": {
                                "__typename": "PathContentConnection",
                                "edges": [
                                    {
                                        "cursor": "0",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileA.py",
                                            "path": "fileA.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                    {
                                        "cursor": "1",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileB.py",
                                            "path": "fileB.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                    {
                                        "cursor": "2",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileB.py",
                                            "path": "folder/fileB.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                    {
                                        "cursor": "3",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileC.py",
                                            "path": "folder/subfolder/fileC.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                    {
                                        "cursor": "4",
                                        "node": {
                                            "__typename": "PathContentFile",
                                            "name": "fileD.py",
                                            "path": "folder/subfolder/fileD.py",
                                            "hits": 8,
                                            "misses": 0,
                                            "partials": 0,
                                            "lines": 10,
                                            "percentCovered": 80.0,
                                            "isCriticalFile": False,
                                        },
                                    },
                                ],
                                "totalCount": 5,
                                "pageInfo": {
                                    "hasNextPage": False,
                                    "hasPreviousPage": False,
                                    "startCursor": "0",
                                    "endCursor": "4",
                                },
                            }
                        }
                    }
                }
            }
        }
