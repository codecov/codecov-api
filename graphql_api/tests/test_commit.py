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
from graphql_api.types.enums import CommitStatus, UploadErrorEnum, UploadState
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
        MockLines()
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
    def setUp(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.author = OwnerFactory()
        self.parent_commit = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(
            repository=self.repo,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=self.parent_commit.commitid,
        )
        self.report = CommitReportFactory(commit=self.commit)

        # mock reports for all tests in this class
        self.head_report_patcher = patch(
            "services.comparison.Comparison.head_report", new_callable=PropertyMock
        )
        self.head_report = self.head_report_patcher.start()
        self.head_report.return_value = None
        self.addCleanup(self.head_report_patcher.stop)
        self.base_report_patcher = patch(
            "services.comparison.Comparison.base_report", new_callable=PropertyMock
        )
        self.base_report = self.base_report_patcher.start()
        self.base_report.return_value = None
        self.addCleanup(self.base_report_patcher.stop)

    def test_fetch_commit(self):
        query = (
            query_commit
            % """
            message,
            createdAt,
            commitid,
            state,
            author { username }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["commitid"] == self.commit.commitid
        assert commit["message"] == self.commit.message
        assert commit["author"]["username"] == self.commit.author.username
        assert commit["state"] == self.commit.state

    def test_fetch_commits(self):
        query = query_commits % "message,commitid,ciPassed"
        self.repo_2 = RepositoryFactory(
            author=self.org, name="test-repo", private=False
        )

        CommitFactory(
            repository=self.repo_2,
            commitid=123,
            timestamp=datetime.today() - timedelta(days=3),
        )
        CommitFactory(
            repository=self.repo_2,
            commitid=456,
            timestamp=datetime.today() - timedelta(days=1),
        )
        CommitFactory(
            repository=self.repo_2,
            commitid=789,
            timestamp=datetime.today() - timedelta(days=2),
        )

        variables = {"org": self.org.username, "repo": self.repo_2.name}
        data = self.gql_request(query, variables=variables)
        commits = paginate_connection(data["owner"]["repository"]["commits"])
        commits_commitids = [commit["commitid"] for commit in commits]
        assert commits_commitids == ["456", "789", "123"]

    def test_fetch_parent_commit(self):
        query = query_commit % "parent { commitid } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["parent"]["commitid"] == self.parent_commit.commitid

    def test_resolve_commit_without_parent(self):
        self.commit_without_parent = CommitFactory(
            repository=self.repo, parent_commit_id=None
        )
        query = query_commit % "parent { commitid } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit_without_parent.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["parent"] is None

    def test_fetch_commit_coverage(self):
        ReportLevelTotalsFactory(report=self.report, coverage=12)
        query = query_commit % "totals { coverage } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["totals"]["coverage"] == 12

    def test_fetch_commit_build(self):
        session_one = UploadFactory(report=self.report, provider="circleci")
        session_two = UploadFactory(report=self.report, provider="travisci")
        query = query_commit % "uploads { edges { node { provider } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        builds = paginate_connection(commit["uploads"])
        assert builds == [
            {"provider": session_one.provider},
            {"provider": session_two.provider},
        ]

    def test_fetch_commit_uploads_state(self):
        UploadFactory(
            report=self.report, provider="circleci", state=UploadState.PROCESSED.value
        )
        UploadFactory(
            report=self.report, provider="travisci", state=UploadState.ERROR.value
        )
        UploadFactory(
            report=self.report, provider="travisci", state=UploadState.COMPLETE.value
        )
        UploadFactory(
            report=self.report, provider="travisci", state=UploadState.UPLOADED.value
        )
        UploadFactory(
            report=self.report, provider="travisci", state=UploadState.EMPTY.value
        )
        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        state
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])

        assert uploads == [
            {"state": UploadState.PROCESSED.name},
            {"state": UploadState.ERROR.name},
            {"state": UploadState.COMPLETE.name},
            {"state": UploadState.UPLOADED.name},
            {"state": UploadState.EMPTY.name},
        ]

    def test_fetch_commit_uploads(self):
        flag_a = RepositoryFlagFactory(flag_name="flag_a")
        flag_b = RepositoryFlagFactory(flag_name="flag_b")
        flag_c = RepositoryFlagFactory(flag_name="flag_c")
        flag_d = RepositoryFlagFactory(flag_name="flag_d")

        session_a = UploadFactory(
            report=self.report,
            upload_type=UploadType.UPLOADED.value,
            order_number=0,
        )
        UploadFlagMembershipFactory(report_session=session_a, flag=flag_a)
        UploadFlagMembershipFactory(report_session=session_a, flag=flag_b)
        UploadFlagMembershipFactory(report_session=session_a, flag=flag_c)
        session_b = UploadFactory(
            report=self.report,
            upload_type=UploadType.CARRIEDFORWARD.value,
            order_number=1,
        )
        UploadFlagMembershipFactory(report_session=session_b, flag=flag_a)

        session_c = UploadFactory(
            report=self.report,
            upload_type=UploadType.CARRIEDFORWARD.value,
            order_number=2,
        )
        UploadFlagMembershipFactory(report_session=session_c, flag=flag_b)
        session_d = UploadFactory(
            report=self.report,
            upload_type=UploadType.UPLOADED.value,
            order_number=3,
        )
        UploadFlagMembershipFactory(report_session=session_d, flag=flag_b)

        session_e = UploadFactory(
            report=self.report,
            upload_type=UploadType.CARRIEDFORWARD.value,
            order_number=4,
        )
        UploadFlagMembershipFactory(report_session=session_e, flag=flag_d)
        UploadFactory(
            report=self.report,
            upload_type=UploadType.UPLOADED.value,
            order_number=5,
        )

        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        id
                        uploadType
                        flags
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])

        # ordered by upload id, omits uploads with carriedforward flag if another
        # upload exists with the same flag name is is not carriedforward

        assert uploads == [
            {
                "id": 0,
                "uploadType": "UPLOADED",
                "flags": ["flag_a", "flag_b", "flag_c"],
            },
            # TEMP: we're returning ALL uploads for now while we figure out a more
            # performant way to make this query
            {"id": 1, "uploadType": "CARRIEDFORWARD", "flags": ["flag_a"]},
            {"id": 2, "uploadType": "CARRIEDFORWARD", "flags": ["flag_b"]},
            {"id": 3, "uploadType": "UPLOADED", "flags": ["flag_b"]},
            {"id": 4, "uploadType": "CARRIEDFORWARD", "flags": ["flag_d"]},
            {"id": 5, "uploadType": "UPLOADED", "flags": []},
        ]

    def test_fetch_commit_uploads_no_report(self):
        commit = CommitFactory(
            repository=self.repo,
            parent_commit_id=self.commit.commitid,
        )
        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        uploadType
                        flags
                        provider
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])
        assert uploads == []

    def test_fetch_commit_uploads_errors(self):
        session = UploadFactory(
            report=self.report, provider="circleci", state=UploadState.ERROR.value
        )
        UploadErrorFactory(
            report_session=session, error_code=UploadErrorEnum.REPORT_EXPIRED.value
        )
        UploadErrorFactory(
            report_session=session, error_code=UploadErrorEnum.FILE_NOT_IN_STORAGE.value
        )

        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        errors {
                            edges {
                                node {
                                    errorCode
                                }
                            }
                        }
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        [upload] = paginate_connection(commit["uploads"])
        errors = paginate_connection(upload["errors"])

        assert errors == [
            {"errorCode": UploadErrorEnum.REPORT_EXPIRED.name},
            {"errorCode": UploadErrorEnum.FILE_NOT_IN_STORAGE.name},
        ]

    def test_yaml_return_default_state_if_default(self):
        org = OwnerFactory(username="default_yaml_owner")
        repo = RepositoryFactory(author=org, private=False)
        commit = CommitFactory(repository=repo)
        query = (
            query_commit
            % """
            yamlState
        """
        )
        variables = {
            "org": org.username,
            "repo": repo.name,
            "commit": commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["commit"]["yamlState"] == "DEFAULT"

    def test_fetch_commit_ci(self):
        UploadFactory(
            report=self.report,
            provider="circleci",
            job_code=123,
            build_code=456,
        )
        query = query_commit % "uploads { edges { node { ciUrl } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])
        assert uploads == [
            {
                "ciUrl": "https://circleci.com/gh/codecov/gazebo/456#tests/containers/123",
            }
        ]

    def test_fetch_download_url(self):
        upload = UploadFactory(
            report=self.report,
            storage_path="v4/raw/2022-06-23/942173DE95CBF167C5683F40B7DB34C0/ee3ecad424e67419d6c4531540f1ef5df045ff12/919ccc6d-7972-4895-b289-f2d569683a17.txt",
        )
        query = query_commit % "uploads { edges { node { downloadUrl } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])
        assert uploads == [
            {
                "downloadUrl": f"https://testserver/upload/gh/{self.org.username}/{self.repo.name}/download?path={upload.storage_path}",
            }
        ]

    @patch(
        "core.commands.commit.commit.CommitCommands.get_final_yaml",
        new_callable=AsyncMock,
    )
    def test_fetch_commit_yaml_call_the_command(self, command_mock):
        query = query_commit % "yaml"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_config = {"codecov": "yes"}
        command_mock.return_value = fake_config
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["yaml"] == yaml.dump(fake_config)

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("core.commands.commit.commit.CommitCommands.get_file_content")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_commit_coverage_file_call_the_command(
        self, report_mock, content_mock, critical_files
    ):
        query = (
            query_commit
            % 'coverageFile(path: "path") { hashedPath, content, isCriticalFile, coverage { line,coverage }, totals {coverage} }'
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        fake_coverage = {
            "content": "file content",
            "coverage": [
                {"line": 0, "coverage": "P"},
                {"line": 1, "coverage": "H"},
                {"line": 2, "coverage": "M"},
            ],
            "totals": {"coverage": 83.0},
        }
        content_mock.return_value = "file content"
        critical_files.return_value = [CriticalFile("path")]

        report_mock.return_value = MockReport()
        data = self.gql_request(query, variables=variables)
        coverageFile = data["owner"]["repository"]["commit"]["coverageFile"]
        assert coverageFile["content"] == fake_coverage["content"]
        assert coverageFile["coverage"] == fake_coverage["coverage"]
        assert coverageFile["totals"] == fake_coverage["totals"]
        assert coverageFile["isCriticalFile"] == True
        assert coverageFile["hashedPath"] == hashlib.md5("path".encode()).hexdigest()

    @patch("services.components.component_filtered_report")
    @patch("services.components.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_commit_coverage_file_with_components(
        self, report_mock, commit_components_mock, filtered_mock
    ):
        components = ["Global"]

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
            "components": components,
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
                    "paths": ["**/*.py"],
                }
            ),
        ]
        filtered_mock.return_value = MockReport()

        query_files = """
        query FetchCommit($org: String!, $repo: String!, $commit: String!, $components: [String!]!) {
            owner(username: $org) {
                repository(name: $repo) {
                    ... on Repository {
                        commit(id: $commit) {
                            coverageFile(path: "path", components: $components) {
                                hashedPath, content, isCriticalFile, coverage { line,coverage }, totals {coverage}
                            }
                        }
                    }
                }
            }
        }
        """

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageFile": {
                            "content": None,
                            "coverage": [
                                {"coverage": "P", "line": 0},
                                {"coverage": "H", "line": 1},
                                {"coverage": "M", "line": 2},
                            ],
                            "hashedPath": "d6fe1d0be6347b8ef2427fa629c04485",
                            "isCriticalFile": False,
                            "totals": {"coverage": 83.0},
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("core.commands.commit.commit.CommitCommands.get_file_content")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_fetch_commit_with_no_coverage_data(
        self, report_mock, content_mock, critical_files
    ):
        query = (
            query_commit
            % 'coverageFile(path: "path") { content, isCriticalFile, coverage { line,coverage }, totals {coverage} }'
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        fake_coverage = {"content": "file content", "coverage": [], "totals": None}
        content_mock.return_value = "file content"
        critical_files.return_value = []

        report_mock.return_value = EmptyReport()
        data = self.gql_request(query, variables=variables)
        coverageFile = data["owner"]["repository"]["commit"]["coverageFile"]
        assert coverageFile["content"] == fake_coverage["content"]
        assert coverageFile["coverage"] == fake_coverage["coverage"]
        assert coverageFile["totals"] == fake_coverage["totals"]
        assert coverageFile["isCriticalFile"] == False

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_flag_names(self, report_mock):
        query = query_commit % "flagNames"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        report_mock.return_value = MockReport()
        data = self.gql_request(query, variables=variables)
        flags = data["owner"]["repository"]["commit"]["flagNames"]
        assert flags == ["flag_a", "flag_b"]

    def test_fetch_commit_compare_call_the_command(self):
        CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
        )
        query = query_commit % "compareWithParent { ... on Comparison { state } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"] == {"state": "pending"}

    def test_fetch_commit_compare_no_parent(self):
        self.commit.parent_commit_id = None
        self.commit.save()

        query = (
            query_commit
            % """
            compareWithParent { __typename ... on Comparison { state } }
            bundleAnalysisCompareWithParent { __typename ... on BundleAnalysisComparison { bundleData { size { uncompress } } } }
            """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["__typename"] == "MissingBaseCommit"
        assert (
            commit["bundleAnalysisCompareWithParent"]["__typename"]
            == "MissingBaseCommit"
        )

    def test_compare_with_parent_comparison_missing_when_commit_comparison_state_is_errored(
        self,
    ):
        CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.ERROR,
        )
        query = (
            query_commit
            % "compareWithParent { __typename ... on Comparison { state } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["__typename"] == "MissingComparison"

    def test_compare_with_parent_change_coverage(self):
        CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )
        ReportLevelTotalsFactory(
            report=CommitReportFactory(commit=self.parent_commit),
            coverage=75.0,
            files=0,
            lines=0,
            hits=0,
            misses=0,
            partials=0,
            branches=0,
            methods=0,
        )
        ReportLevelTotalsFactory(
            report=self.report,
            coverage=80.0,
            files=0,
            lines=0,
            hits=0,
            misses=0,
            partials=0,
            branches=0,
            methods=0,
        )

        query = (
            query_commit % "compareWithParent { ... on Comparison { changeCoverage } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["changeCoverage"] == 5.0

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_compare(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        base_commit_report = CommitReportFactory(
            commit=self.parent_commit,
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )
        head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = (
            query_commit
            % """
            bundleAnalysisCompareWithParent {
                __typename
                ... on BundleAnalysisComparison {
                    bundles {
                        name
                        changeType
                        bundleData {
                            size {
                                uncompress
                            }
                        }
                        bundleChange {
                            size {
                                uncompress
                            }
                        }
                    }
                    bundleData {
                        size {
                            uncompress
                        }
                    }
                    bundleChange {
                        size {
                            uncompress
                        }
                    }
                }
            }
            """
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["bundleAnalysisCompareWithParent"] == {
            "__typename": "BundleAnalysisComparison",
            "bundles": [
                {
                    "name": "b1",
                    "changeType": "changed",
                    "bundleData": {"size": {"uncompress": 20}},
                    "bundleChange": {"size": {"uncompress": 5}},
                },
                {
                    "name": "b2",
                    "changeType": "changed",
                    "bundleData": {"size": {"uncompress": 200}},
                    "bundleChange": {"size": {"uncompress": 50}},
                },
                {
                    "name": "b3",
                    "changeType": "added",
                    "bundleData": {"size": {"uncompress": 1500}},
                    "bundleChange": {"size": {"uncompress": 1500}},
                },
                {
                    "name": "b5",
                    "changeType": "changed",
                    "bundleData": {"size": {"uncompress": 200000}},
                    "bundleChange": {"size": {"uncompress": 50000}},
                },
                {
                    "name": "b4",
                    "changeType": "removed",
                    "bundleData": {"size": {"uncompress": 0}},
                    "bundleChange": {"size": {"uncompress": -15000}},
                },
            ],
            "bundleData": {"size": {"uncompress": 201720}},
            "bundleChange": {"size": {"uncompress": 36555}},
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_sqlite_file_deleted(self, get_storage_service):
        os.system("rm -rf /tmp/bundle_analysis_*")
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        base_commit_report = CommitReportFactory(
            commit=self.parent_commit,
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )
        head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = (
            query_commit
            % """
            bundleAnalysisCompareWithParent {
                __typename
                ... on BundleAnalysisComparison {
                    bundleData {
                        size {
                            uncompress
                        }
                    }
                }
            }
            """
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        self.gql_request(query, variables=variables)

        for file in os.listdir("/tmp"):
            assert not file.startswith("bundle_analysis_")
        os.system("rm -rf /tmp/bundle_analysis_*")

    @patch("graphql_api.views.os.unlink")
    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_sqlite_file_not_deleted(
        self, get_storage_service, os_unlink_mock
    ):
        os.system("rm -rf /tmp/bundle_analysis_*")
        os_unlink_mock.side_effect = Exception("something went wrong")
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        base_commit_report = CommitReportFactory(
            commit=self.parent_commit,
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )
        head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = (
            query_commit
            % """
            bundleAnalysisCompareWithParent {
                __typename
                ... on BundleAnalysisComparison {
                    bundleData {
                        size {
                            uncompress
                        }
                    }
                }
            }
            """
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        self.gql_request(query, variables=variables)

        found = False
        for file in os.listdir("/tmp"):
            if file.startswith("bundle_analysis_"):
                found = True
                break
        assert found
        os.system("rm -rf /tmp/bundle_analysis_*")

    def test_bundle_analysis_missing_report(self):
        query = (
            query_commit
            % """
            bundleAnalysisReport {
                __typename
                ... on MissingHeadReport {
                    message
                }
            }
            """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysisReport"] == {
            "__typename": "MissingHeadReport",
            "message": "Missing head report",
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_report(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchCommit($org: String!, $repo: String!, $commit: String!) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysisReport {
                                    __typename
                                    ... on BundleAnalysisReport {
                                        bundles {
                                            name
                                            assets {
                                                normalizedName
                                            }
                                            asset(name: "not_exist") {
                                                normalizedName
                                            }
                                            bundleData {
                                                loadTime {
                                                    threeG
                                                    highSpeed
                                                }
                                                size {
                                                    gzip
                                                    uncompress
                                                }
                                            }
                                        }
                                        bundleData {
                                            loadTime {
                                                threeG
                                                highSpeed
                                            }
                                            size {
                                                gzip
                                                uncompress
                                            }
                                        }
                                        bundle(name: "not_exist") {
                                            name
                                        }
                                    }
                                    ... on MissingHeadReport {
                                        message
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundles": [
                {
                    "name": "b1",
                    "assets": [
                        {"normalizedName": "assets/react-*.svg"},
                        {"normalizedName": "assets/index-*.css"},
                        {"normalizedName": "assets/LazyComponent-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                    ],
                    "asset": None,
                    "bundleData": {
                        "loadTime": {
                            "threeG": 0,
                            "highSpeed": 0,
                        },
                        "size": {
                            "gzip": 0,
                            "uncompress": 20,
                        },
                    },
                },
                {
                    "name": "b2",
                    "assets": [
                        {"normalizedName": "assets/react-*.svg"},
                        {"normalizedName": "assets/index-*.css"},
                        {"normalizedName": "assets/LazyComponent-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                    ],
                    "asset": None,
                    "bundleData": {
                        "loadTime": {
                            "threeG": 2,
                            "highSpeed": 0,
                        },
                        "size": {
                            "gzip": 0,
                            "uncompress": 200,
                        },
                    },
                },
                {
                    "name": "b3",
                    "assets": [
                        {"normalizedName": "assets/react-*.svg"},
                        {"normalizedName": "assets/index-*.css"},
                        {"normalizedName": "assets/LazyComponent-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                    ],
                    "asset": None,
                    "bundleData": {
                        "loadTime": {
                            "threeG": 16,
                            "highSpeed": 0,
                        },
                        "size": {
                            "gzip": 1,
                            "uncompress": 1500,
                        },
                    },
                },
                {
                    "name": "b5",
                    "assets": [
                        {"normalizedName": "assets/react-*.svg"},
                        {"normalizedName": "assets/index-*.css"},
                        {"normalizedName": "assets/LazyComponent-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                        {"normalizedName": "assets/index-*.js"},
                    ],
                    "asset": None,
                    "bundleData": {
                        "loadTime": {
                            "threeG": 2133,
                            "highSpeed": 53,
                        },
                        "size": {
                            "gzip": 200,
                            "uncompress": 200000,
                        },
                    },
                },
            ],
            "bundleData": {
                "loadTime": {
                    "threeG": 2151,
                    "highSpeed": 53,
                },
                "size": {
                    "gzip": 201,
                    "uncompress": 201720,
                },
            },
            "bundle": None,
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_asset(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        with open(
            "./services/tests/samples/bundle_with_assets_and_modules.sqlite", "rb"
        ) as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchCommit($org: String!, $repo: String!, $commit: String!) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysisReport {
                                    __typename
                                    ... on BundleAnalysisReport {
                                        bundle(name: "b5") {
                                            moduleCount
                                            asset(name: "assets/LazyComponent-fcbb0922.js") {
                                                name
                                                normalizedName
                                                extension
                                                bundleData {
                                                    loadTime {
                                                        threeG
                                                        highSpeed
                                                    }
                                                    size {
                                                        gzip
                                                        uncompress
                                                    }
                                                }
                                                modules {
                                                    name
                                                    bundleData {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        bundle_report = commit["bundleAnalysisReport"]["bundle"]
        asset_report = bundle_report["asset"]

        assert bundle_report is not None
        assert bundle_report["moduleCount"] == 7

        assert asset_report is not None
        assert asset_report["name"] == "assets/LazyComponent-fcbb0922.js"
        assert asset_report["normalizedName"] == "assets/LazyComponent-*.js"
        assert asset_report["extension"] == "js"
        assert asset_report["bundleData"] == {
            "loadTime": {
                "threeG": 320,
                "highSpeed": 8,
            },
            "size": {
                "gzip": 30,
                "uncompress": 30000,
            },
        }

        modules = sorted(asset_report["modules"], key=lambda m: m["name"])

        assert modules and len(modules) == 3
        assert modules[0] == {
            "name": "./src/LazyComponent/LazyComponent",
            "bundleData": {
                "loadTime": {
                    "threeG": 64,
                    "highSpeed": 1,
                },
                "size": {
                    "gzip": 6,
                    "uncompress": 6000,
                },
            },
        }
        assert modules[1] == {
            "name": "./src/LazyComponent/LazyComponent.tsx",
            "bundleData": {
                "loadTime": {
                    "threeG": 53,
                    "highSpeed": 1,
                },
                "size": {
                    "gzip": 5,
                    "uncompress": 5000,
                },
            },
        }
        assert modules[2] == {
            "name": "./src/LazyComponent/LazyComponent.tsx?module",
            "bundleData": {
                "loadTime": {
                    "threeG": 53,
                    "highSpeed": 1,
                },
                "size": {
                    "gzip": 4,
                    "uncompress": 4970,
                },
            },
        }

    def test_compare_with_parent_missing_change_coverage(self):
        CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )
        ReportLevelTotalsFactory(
            report=CommitReportFactory(commit=self.parent_commit),
            coverage=75.0,
            files=0,
            lines=0,
            hits=0,
            misses=0,
            partials=0,
            branches=0,
            methods=0,
        )

        query = (
            query_commit % "compareWithParent { ... on Comparison { changeCoverage } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["changeCoverage"] is None

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    def test_commit_critical_files(self, critical_files):
        critical_files.return_value = [
            CriticalFile("one"),
            CriticalFile("two"),
            CriticalFile("three"),
        ]

        query = query_commit % "criticalFiles { name }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["criticalFiles"] == [
            {"name": "one"},
            {"name": "two"},
            {"name": "three"},
        ]

    def test_commit_yaml_errors(self):
        CommitErrorFactory(commit=self.commit, error_code="invalid_yaml")
        CommitErrorFactory(commit=self.commit, error_code="yaml_client_error")
        query = (
            query_commit
            % "errors(errorType: YAML_ERROR) { edges { node { errorCode } } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        errors = paginate_connection(commit["errors"])
        assert errors == [
            {"errorCode": "invalid_yaml"},
            {"errorCode": "yaml_client_error"},
        ]

    def test_commit_bot_errors(self):
        CommitErrorFactory(commit=self.commit, error_code="repo_bot_invalid")
        CommitErrorFactory(commit=self.commit, error_code="repo_bot_invalid")
        query = (
            query_commit
            % "errors(errorType: BOT_ERROR) { edges { node { errorCode } } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        errors = paginate_connection(commit["errors"])
        assert errors == [
            {"errorCode": "repo_bot_invalid"},
            {"errorCode": "repo_bot_invalid"},
        ]

    def test_fetch_upload_name(self):
        UploadFactory(
            name="First Upload",
            report=self.report,
            job_code=123,
            build_code=456,
        )
        query = query_commit % "uploads { edges { node { name } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])
        assert uploads == [
            {
                "name": "First Upload",
            }
        ]

    @patch("services.comparison.Comparison.validate")
    def test_has_different_number_of_head_and_base_reports_with_invalid_comparison(
        self, mock_compare_validate
    ):
        CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )
        mock_compare_validate.side_effect = MissingComparisonReport()
        query = (
            query_commit
            % "compareWithParent { ... on Comparison { hasDifferentNumberOfHeadAndBaseReports } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "compareWithParent": {
                            "hasDifferentNumberOfHeadAndBaseReports": False
                        }
                    }
                }
            }
        }

    def test_fetch_upload_name_is_none(self):
        UploadFactory(
            report=self.report,
            job_code=123,
            build_code=456,
        )
        query = query_commit % "uploads { edges { node { name } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])
        assert uploads == [
            {
                "name": None,
            }
        ]

    def test_fetch_uploads_number(self):
        for i in range(25):
            UploadFactory(
                report=self.report,
                job_code=123,
                build_code=456,
            )
        query = query_commit % "totalUploads"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["commit"]["totalUploads"] == 25

    def test_fetch_all_uploads_is_the_default(self):
        for i in range(100):
            UploadFactory(
                report=self.report,
                job_code=123,
                build_code=456,
            )
        query = query_commit % "uploads { edges { node { state } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert len(data["owner"]["repository"]["commit"]["uploads"]["edges"]) == 100

    def test_fetch_paginated_uploads(self):
        for i in range(99):
            UploadFactory(
                report=self.report,
                job_code=123,
                build_code=456,
            )
        query = (
            query_commit
            % "totalUploads, uploads(first: 25) { edges { node { state } } }"
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert (data["owner"]["repository"]["commit"]["totalUploads"]) == 99
        assert len(data["owner"]["repository"]["commit"]["uploads"]["edges"]) == 25

    def test_fetch_commit_status_no_reports(self):
        query = (
            query_commit
            % """
            coverageStatus
            bundleStatus
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["coverageStatus"] is None
        assert commit["bundleStatus"] is None

    def test_fetch_commit_status_no_sessions(self):
        CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.COVERAGE
        )
        CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )
        query = (
            query_commit
            % """
            coverageStatus
            bundleStatus
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["coverageStatus"] is None
        assert commit["bundleStatus"] is None

    def test_fetch_commit_status_completed(self):
        coverage_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=coverage_report, state="processed")
        UploadFactory(report=coverage_report, state="processed")
        UploadFactory(report=coverage_report, state="fully_overwritten")
        UploadFactory(report=coverage_report, state="partially_overwritten")

        ba_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )
        UploadFactory(report=ba_report, state="processed")
        UploadFactory(report=ba_report, state="processed")
        UploadFactory(report=ba_report, state="fully_overwritten")
        UploadFactory(report=ba_report, state="partially_overwritten")

        query = (
            query_commit
            % """
            coverageStatus
            bundleStatus
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["coverageStatus"] == CommitStatus.COMPLETED.value
        assert commit["bundleStatus"] == CommitStatus.COMPLETED.value

    def test_fetch_commit_status_error(self):
        coverage_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=coverage_report, state="processed")
        UploadFactory(report=coverage_report, state="error")
        UploadFactory(report=coverage_report, state="uploaded")
        UploadFactory(report=coverage_report, state="partially_overwritten")

        ba_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )
        UploadFactory(report=ba_report, state="processed")
        UploadFactory(report=ba_report, state="error")
        UploadFactory(report=ba_report, state="uploaded")
        UploadFactory(report=ba_report, state="partially_overwritten")

        query = (
            query_commit
            % """
            coverageStatus
            bundleStatus
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["coverageStatus"] == CommitStatus.ERROR.value
        assert commit["bundleStatus"] == CommitStatus.ERROR.value

    def test_fetch_commit_status_pending(self):
        coverage_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.COVERAGE
        )
        UploadFactory(report=coverage_report, state="processed")
        UploadFactory(report=coverage_report, state="processed")
        UploadFactory(report=coverage_report, state="uploaded")
        UploadFactory(report=coverage_report, state="partially_overwritten")

        ba_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )
        UploadFactory(report=ba_report, state="processed")
        UploadFactory(report=ba_report, state="processed")
        UploadFactory(report=ba_report, state="uploaded")
        UploadFactory(report=ba_report, state="partially_overwritten")

        query = (
            query_commit
            % """
            coverageStatus
            bundleStatus
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["coverageStatus"] == CommitStatus.PENDING.value
        assert commit["bundleStatus"] == CommitStatus.PENDING.value
