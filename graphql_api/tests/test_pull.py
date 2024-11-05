import os
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.api_archive.archive import ArchiveService
from shared.bundle_analysis import StoragePaths
from shared.bundle_analysis.storage import get_bucket_name
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.storage.memory import MemoryStorageService

from compare.tests.factories import CommitComparisonFactory
from core.models import Commit
from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory, ReportLevelTotalsFactory

from .helper import GraphQLTestHelper, paginate_connection

query_list_pull_request = """{
    me {
        owner {
            repository(name: "test-repo-for-pull") {
                ... on Repository {
                    name
                    pulls {
                        edges {
                            node {
                                title
                                pullId
                            }
                        }
                    }
                }
            }
        }
    }
}
"""

default_pull_request_detail_query = """
    title
    state
    pullId
    updatestamp
    author {
        username
    }
    head {
        coverageAnalytics {
            totals {
                coverage
            }
        }
    }
    comparedTo {
        commitid
    }
    compareWithBase {
        __typename
        ... on Comparison {
            patchTotals {
                coverage
            }
        }
    }
    behindBy
    behindByCommit
"""

pull_request_detail_query_with_bundle_analysis = """
    title
    state
    pullId
    updatestamp
    author {
        username
    }
    head {
        coverageAnalytics {
            totals {
                coverage
            }
        }
    }
    comparedTo {
        commitid
    }
    compareWithBase {
        __typename
        ... on Comparison {
            patchTotals {
                coverage
            }
        }
    }
    bundleAnalysisCompareWithBase {
        __typename
        ... on BundleAnalysisComparison {
            bundleData {
                size {
                    uncompress
                }
            }
        }
    }
    behindBy
    behindByCommit
"""

pull_request_bundle_analysis_missing_reports = """
    bundleAnalysisCompareWithBase {
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

query_pull_request_detail = """{
    me {
        owner {
            repository(name: "test-repo-for-pull") {
                ... on Repository {
                    name
                    pull(id: %s) {
                        %s
                    }
                }
            }
        }
    }
}
"""


class TestPullRequestList(GraphQLTestHelper, TransactionTestCase):
    def fetch_list_pull_request(self):
        data = self.gql_request(query_list_pull_request, owner=self.owner)
        return paginate_connection(data["me"]["owner"]["repository"]["pulls"])

    def fetch_one_pull_request(self, id, query=default_pull_request_detail_query):
        data = self.gql_request(
            query_pull_request_detail % (id, query), owner=self.owner
        )
        return data["me"]["owner"]["repository"]["pull"]

    def setUp(self):
        self.owner = OwnerFactory(username="test-pull-user")
        self.repository = RepositoryFactory(
            author=self.owner, active=True, private=True, name="test-repo-for-pull"
        )

    def test_fetch_list_pull_request(self):
        pull_1 = PullFactory(repository=self.repository, title="a")
        pull_2 = PullFactory(repository=self.repository, title="b")
        pulls = self.fetch_list_pull_request()
        pull_titles = [pull["title"] for pull in pulls]
        assert pull_1.title in pull_titles
        assert pull_2.title in pull_titles

    @freeze_time("2021-02-02 00:00:00")
    @patch("core.commands.pull.interactors.fetch_pull_request.TaskService")
    def test_when_repository_has_null_compared_to(self, mock_task_service):
        my_pull = PullFactory(
            repository=self.repository,
            title="test-null-base",
            author=self.owner,
            head=CommitFactory(
                repository=self.repository,
                author=self.owner,
                commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            ).commitid,
            compared_to=None,
        )
        with freeze_time("2021-02-02 06:00:00"):
            pull = self.fetch_one_pull_request(
                my_pull.pullid, pull_request_detail_query_with_bundle_analysis
            )
        assert pull == {
            "title": "test-null-base",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": {"coverageAnalytics": {"totals": None}},
            "comparedTo": None,
            "compareWithBase": {
                "__typename": "MissingBaseCommit",
            },
            "bundleAnalysisCompareWithBase": {
                "__typename": "MissingBaseCommit",
            },
            "behindBy": None,
            "behindByCommit": None,
        }
        mock_task_service.return_value.pulls_sync.assert_called_with(
            my_pull.repository.repoid, my_pull.pullid
        )

    @freeze_time("2021-02-02 00:00:00")
    @patch("core.commands.pull.interactors.fetch_pull_request.TaskService")
    def test_when_repository_has_null_author(self, mock_task_service):
        PullFactory(
            repository=self.repository,
            title="dummy-first-pr",
        )
        second_pr = PullFactory(
            repository=self.repository,
            title="test-null-author",
            author=None,
            head=None,
            compared_to=None,
        )
        pull = self.fetch_one_pull_request(
            second_pr.pullid, pull_request_detail_query_with_bundle_analysis
        )
        assert pull == {
            "title": "test-null-author",
            "state": "OPEN",
            "pullId": second_pr.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": None,
            "head": None,
            "comparedTo": None,
            "compareWithBase": {
                "__typename": "MissingBaseCommit",
            },
            "bundleAnalysisCompareWithBase": {
                "__typename": "MissingBaseCommit",
            },
            "behindBy": None,
            "behindByCommit": None,
        }
        mock_task_service.return_value.pulls_sync.assert_not_called()

    @freeze_time("2021-02-02")
    @patch("core.commands.pull.interactors.fetch_pull_request.TaskService")
    def test_when_repository_has_null_head_no_parent_report(self, mock_task_service):
        PullFactory(
            repository=self.repository,
            title="dummy-first-pr",
            author=self.owner,
        )
        second_pr = PullFactory(
            repository=self.repository,
            title="test-null-head",
            author=self.owner,
            head=None,
        )
        pull = self.fetch_one_pull_request(
            second_pr.pullid, pull_request_detail_query_with_bundle_analysis
        )
        assert pull == {
            "title": "test-null-head",
            "state": "OPEN",
            "pullId": second_pr.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": None,
            "comparedTo": None,
            "compareWithBase": {
                "__typename": "MissingHeadCommit",
            },
            "bundleAnalysisCompareWithBase": {
                "__typename": "MissingHeadReport",
            },
            "behindBy": None,
            "behindByCommit": None,
        }
        mock_task_service.return_value.pulls_sync.assert_not_called()

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_when_repository_has_null_head_has_parent_report(self, get_storage_service):
        os.system("rm -rf /tmp/bundle_analysis_*")
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        parent_commit = CommitFactory(repository=self.repository)

        base_commit_report = CommitReportFactory(
            commit=parent_commit,
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )

        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.owner,
            head=None,
            compared_to=base_commit_report.commit.commitid,
            behind_by=23,
            behind_by_commit="1089nf898as-jdf09hahs09fgh",
        )

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repository),
                report_key=base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            bundleAnalysisCompareWithBase {
                __typename
                ... on BundleAnalysisComparison {
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

        pull = self.fetch_one_pull_request(my_pull.pullid, query)

        assert pull == {
            "bundleAnalysisCompareWithBase": {
                "__typename": "BundleAnalysisComparison",
                "bundleData": {
                    "size": {
                        "uncompress": 165165,
                    }
                },
                "bundleChange": {
                    "size": {
                        "uncompress": 0,
                    }
                },
            }
        }

        for file in os.listdir("/tmp"):
            assert not file.startswith("bundle_analysis_")

        os.system("rm -rf /tmp/bundle_analysis_*")

    @freeze_time("2021-02-02")
    def test_when_pr_is_first_pr_in_repo(self):
        first_pr = PullFactory(
            repository=self.repository,
            title="dummy-first-pr",
            author=self.owner,
            compared_to=None,
        )

        res = self.fetch_one_pull_request(
            first_pr.pullid, pull_request_detail_query_with_bundle_analysis
        )
        assert res == {
            "title": "dummy-first-pr",
            "state": "OPEN",
            "pullId": first_pr.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": None,
            "comparedTo": None,
            "compareWithBase": {
                "__typename": "FirstPullRequest",
            },
            "bundleAnalysisCompareWithBase": {
                "__typename": "FirstPullRequest",
            },
            "behindBy": None,
            "behindByCommit": None,
        }

    @freeze_time("2021-02-02")
    def test_when_repository_has_missing_head_commit(self):
        PullFactory(
            repository=self.repository,
            title="test-missing-head-commit",
            author=self.owner,
        )
        second_pull = PullFactory(
            repository=self.repository,
            title="second-pr-so-it-doesn't-fetch-first-pr",
            author=self.owner,
        )
        Commit.objects.filter(
            repository_id=self.repository.pk,
            commitid=second_pull.head,
        ).delete()

        res = self.fetch_one_pull_request(second_pull.pullid)
        assert res == {
            "title": "second-pr-so-it-doesn't-fetch-first-pr",
            "state": "OPEN",
            "pullId": second_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": None,
            "comparedTo": None,
            "compareWithBase": {
                "__typename": "MissingComparison",
            },
            "behindBy": None,
            "behindByCommit": None,
        }

    @freeze_time("2021-02-02")
    def test_with_complete_pull_request(self):
        head = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            totals={"c": "78.38", "diff": [0, 0, 0, 0, 0, "14"]},
        )
        report = CommitReportFactory(commit=head)
        ReportLevelTotalsFactory(report=report, coverage=78.38)
        compared_to = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s",
        )
        CommitComparisonFactory(
            base_commit=compared_to,
            compare_commit=head,
            patch_totals={"coverage": 0.8739},
        )
        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.owner,
            head=head.commitid,
            compared_to=compared_to.commitid,
            behind_by=23,
            behind_by_commit="1089nf898as-jdf09hahs09fgh",
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-pull-request",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": {"coverageAnalytics": {"totals": {"coverage": 78.38}}},
            "comparedTo": {"commitid": "9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s"},
            "compareWithBase": {
                "__typename": "Comparison",
                "patchTotals": {"coverage": 87.39},
            },
            "behindBy": 23,
            "behindByCommit": "1089nf898as-jdf09hahs09fgh",
        }

    def test_compare_bundle_analysis_missing_reports(self):
        head = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            totals={"c": "78.38", "diff": [0, 0, 0, 0, 0, "14"]},
        )
        compared_to = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s",
        )

        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.owner,
            head=head.commitid,
            compared_to=compared_to.commitid,
            behind_by=23,
            behind_by_commit="1089nf898as-jdf09hahs09fgh",
        )

        pull = self.fetch_one_pull_request(
            my_pull.pullid, pull_request_bundle_analysis_missing_reports
        )
        assert pull == {
            "bundleAnalysisCompareWithBase": {"__typename": "MissingHeadReport"}
        }

        CommitReportFactory(
            commit=head, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        pull = self.fetch_one_pull_request(
            my_pull.pullid, pull_request_bundle_analysis_missing_reports
        )
        assert pull == {
            "bundleAnalysisCompareWithBase": {"__typename": "MissingBaseReport"}
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_sqlite_file_deleted(self, get_storage_service):
        os.system("rm -rf /tmp/bundle_analysis_*")
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        parent_commit = CommitFactory(repository=self.repository)
        commit = CommitFactory(
            repository=self.repository,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=parent_commit.commitid,
        )

        base_commit_report = CommitReportFactory(
            commit=parent_commit,
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )
        head_commit_report = CommitReportFactory(
            commit=commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.owner,
            head=head_commit_report.commit.commitid,
            compared_to=base_commit_report.commit.commitid,
            behind_by=23,
            behind_by_commit="1089nf898as-jdf09hahs09fgh",
        )

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repository),
                report_key=base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repository),
                report_key=head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            bundleAnalysisCompareWithBase {
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

        pull = self.fetch_one_pull_request(my_pull.pullid, query)

        assert pull == {
            "bundleAnalysisCompareWithBase": {
                "__typename": "BundleAnalysisComparison",
                "bundleData": {
                    "size": {
                        "uncompress": 201720,
                    }
                },
            }
        }

        for file in os.listdir("/tmp"):
            assert not file.startswith("bundle_analysis_")

        os.system("rm -rf /tmp/bundle_analysis_*")

    @freeze_time("2021-02-02")
    def test_pull_no_patch_totals(self):
        head = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="5672734ij1n234918231290j12nasdfioasud0f9",
            totals=None,
        )
        report = CommitReportFactory(commit=head)
        ReportLevelTotalsFactory(report=report, coverage=78.38)
        compared_to = CommitFactory(
            repository=self.repository,
            author=self.owner,
            commitid="9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s",
        )
        CommitComparisonFactory(
            base_commit=compared_to, compare_commit=head, patch_totals=None
        )
        my_pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.owner,
            head=head.commitid,
            compared_to=compared_to.commitid,
        )
        pull = self.fetch_one_pull_request(my_pull.pullid)
        assert pull == {
            "title": "test-pull-request",
            "state": "OPEN",
            "pullId": my_pull.pullid,
            "updatestamp": "2021-02-02T00:00:00",
            "author": {"username": "test-pull-user"},
            "head": {"coverageAnalytics": {"totals": {"coverage": 78.38}}},
            "comparedTo": {"commitid": "9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s"},
            "compareWithBase": {
                "__typename": "Comparison",
                "patchTotals": None,
            },
            "behindBy": None,
            "behindByCommit": None,
        }

    @freeze_time("2021-02-02")
    def test_fetch_commits_request(self):
        query = """
            commits {
                totalCount
                edges {
                    node {
                        commitid
                    }
                }
            }
        """
        my_pull = PullFactory(repository=self.repository)

        CommitFactory(
            repository=self.repository,
            pullid=my_pull.pullid,
            commitid="11111",
            timestamp=datetime.today() - timedelta(days=1),
        )
        CommitFactory(
            repository=self.repository,
            pullid=my_pull.pullid,
            commitid="22222",
            timestamp=datetime.today() - timedelta(days=2),
        )
        CommitFactory(
            repository=self.repository,
            pullid=my_pull.pullid,
            commitid="33333",
            timestamp=datetime.today() - timedelta(days=3),
        )
        CommitFactory(
            repository=self.repository,
            pullid=my_pull.pullid,
            commitid="44444",
            timestamp=datetime.today() - timedelta(days=3),
            deleted=True,
        )

        pull = self.fetch_one_pull_request(my_pull.pullid, query)

        assert pull == {
            "commits": {
                "edges": [
                    {"node": {"commitid": "11111"}},
                    {"node": {"commitid": "22222"}},
                    {"node": {"commitid": "33333"}},
                ],
                "totalCount": 3,
            }
        }

    def test_fetch_first_pull(self):
        pull1 = PullFactory(repository=self.repository)
        assert self.fetch_one_pull_request(pull1.pullid, "firstPull") == {
            "firstPull": True
        }
        pull2 = PullFactory(repository=self.repository)
        assert self.fetch_one_pull_request(pull1.pullid, "firstPull") == {
            "firstPull": True
        }
        assert self.fetch_one_pull_request(pull2.pullid, "firstPull") == {
            "firstPull": False
        }
