from collections import namedtuple
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitWithReportFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType

from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory, FlagComparisonFactory
from reports.tests.factories import RepositoryFlagFactory
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

base_query = """{
    me {
        owner {
            repository(name: "%s") {
                ... on Repository {
                    pull(id: %s) {
                        %s
                    }
                }
            }
        }
    }
}
"""

MockSegmentComparison = namedtuple(
    "MockSegmentComparison", ["header", "lines", "has_unintended_changes"]
)
MockLineComparison = namedtuple(
    "MockLineComparison",
    ["number", "coverage", "value", "is_diff", "hit_session_ids"],
)


class TestPullComparison(TransactionTestCase, GraphQLTestHelper):
    def _request(self, query):
        data = self.gql_request(
            base_query % (self.repository.name, self.pull.pullid, query),
            owner=self.owner,
        )
        return data["me"]["owner"]["repository"]["pull"]

    def setUp(self):
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

        self.owner = OwnerFactory()
        self.repository = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
        )
        self.base_commit = CommitWithReportFactory(
            repository=self.repository,
            author=self.owner,
        )
        self.head_commit = CommitWithReportFactory(
            parent_commit_id=self.base_commit.commitid,
            repository=self.repository,
            author=self.owner,
        )
        self.commit_comparison = CommitComparisonFactory(
            base_commit=self.base_commit,
            compare_commit=self.head_commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )
        self.pull = PullFactory(
            pullid=2,
            repository=self.repository,
            author=self.owner,
            head=self.head_commit.commitid,
            compared_to=self.base_commit.commitid,
        )

    def test_pull_comparison_totals(self):
        base_totals = self.base_commit.reports.first().reportleveltotals
        base_totals.coverage = 75.0
        base_totals.files = 1
        base_totals.lines = 6
        base_totals.hits = 3
        base_totals.misses = 2
        base_totals.partials = 1
        base_totals.branches = 0
        base_totals.methods = 0
        base_totals.save()

        head_totals = self.head_commit.reports.first().reportleveltotals
        head_totals.coverage = 75.0
        head_totals.files = 1
        head_totals.lines = 6
        head_totals.hits = 3
        head_totals.misses = 2
        head_totals.partials = 1
        head_totals.branches = 0
        head_totals.methods = 0
        head_totals.save()

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    baseTotals {
                        percentCovered
                        fileCount
                        lineCount
                        hitsCount
                        missesCount
                        partialsCount
                    }
                    headTotals {
                        percentCovered
                        fileCount
                        lineCount
                        hitsCount
                        missesCount
                        partialsCount
                    }
                }
            }
        """

        res = self._request(query)
        totals = {
            "percentCovered": 75.0,
            "fileCount": 1,
            "lineCount": 6,
            "hitsCount": 3,
            "missesCount": 2,
            "partialsCount": 1,
        }
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "baseTotals": totals,
                "headTotals": totals,
            },
        }

    def test_pull_no_flag_comparisons_for_commit_comparison(self):
        # Just running this w/ the commit_comparison in setup will yield nothing
        query = """
            compareWithBase {
                ... on Comparison {
                    flagComparisons {
                        name
                        patchTotals {
                            percentCovered
                        }
                        headTotals {
                            percentCovered
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {"compareWithBase": {"flagComparisons": []}}

    @patch("services.task.TaskService.compute_comparisons")
    def test_pull_different_number_of_head_and_base_reports_without_context(self, _):
        # Just running this w/ the commit_comparison in setup will yield nothing
        query = """
            compareWithBase {
                ... on Comparison {
                    hasDifferentNumberOfHeadAndBaseReports
                }
            }
        """
        self.commit_comparison.delete()
        res = self._request(query)
        assert res == {
            "compareWithBase": {"hasDifferentNumberOfHeadAndBaseReports": False}
        }

    @patch("services.task.TaskService.compute_comparisons")
    def test_pull_component_comparison_without_context(self, _):
        # Just running this w/ the commit_comparison in setup will yield nothing
        query = """
            compareWithBase {
                ... on Comparison {
                    componentComparisons {
                        name
                    }
                }
            }
        """
        self.commit_comparison.delete()
        res = self._request(query)
        assert res == {"compareWithBase": {"componentComparisons": []}}

    def test_pull_flag_comparisons(self):
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository, flag_name="flag_one"
            ),
            head_totals={"coverage": "85.71429"},
            base_totals={"coverage": "92.2973"},
            patch_totals={"coverage": "29.28364"},
        )
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository, flag_name="flag_two"
            ),
            head_totals={"coverage": "75.273820"},
            base_totals={"coverage": "16.293"},
            patch_totals={"coverage": "68.283496"},
        )
        query = """
            compareWithBase {
                ... on Comparison {
                    flagComparisonsCount
                    flagComparisons {
                        name
                        patchTotals {
                            percentCovered
                        }
                        headTotals {
                            percentCovered
                        }
                        baseTotals {
                            percentCovered
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "compareWithBase": {
                "flagComparisonsCount": 2,
                "flagComparisons": [
                    {
                        "name": "flag_one",
                        "patchTotals": {"percentCovered": 29.28364},
                        "headTotals": {"percentCovered": 85.71429},
                        "baseTotals": {"percentCovered": 92.2973},
                    },
                    {
                        "name": "flag_two",
                        "patchTotals": {"percentCovered": 68.283496},
                        "headTotals": {"percentCovered": 75.27382},
                        "baseTotals": {"percentCovered": 16.293},
                    },
                ],
            }
        }

    def test_pull_flag_comparisons_with_filter(self):
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository, flag_name="flag_one"
            ),
            head_totals={"coverage": "85.71429"},
            base_totals={"coverage": "92.2973"},
            patch_totals={"coverage": "29.28364"},
        )
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository, flag_name="flag_two"
            ),
            head_totals={"coverage": "75.273820"},
            base_totals={"coverage": "16.293"},
            patch_totals={"coverage": "68.283496"},
        )
        query = """
            compareWithBase {
                ... on Comparison {
                    flagComparisons(filters: { term: "flag_two"}) {
                        name
                        patchTotals {
                            percentCovered
                        }
                        headTotals {
                            percentCovered
                        }
                        baseTotals {
                            percentCovered
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "compareWithBase": {
                "flagComparisons": [
                    {
                        "name": "flag_two",
                        "patchTotals": {"percentCovered": 68.283496},
                        "headTotals": {"percentCovered": 75.27382},
                        "baseTotals": {"percentCovered": 16.293},
                    },
                ],
            }
        }

    @patch(
        "services.comparison.Comparison.has_different_number_of_head_and_base_sessions",
        new_callable=PropertyMock,
    )
    def test_compare_with_base_has_different_number_of_reports_on_head_and_base(
        self, mock_has_different_number_of_head_and_base_sessions
    ):
        mock_has_different_number_of_head_and_base_sessions.return_value = True
        query = """
            compareWithBase {
                ... on Comparison {
                    hasDifferentNumberOfHeadAndBaseReports
                }
            }
        """

        res = self._request(query)
        assert res == {
            "compareWithBase": {"hasDifferentNumberOfHeadAndBaseReports": True}
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch(
        "services.comparison.ComparisonReport.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_impacted_files(self, files_mock, critical_files):
        base_report_totals = ReportTotals(
            coverage=75.0,
            files=1,
            lines=6,
            hits=3,
            misses=2,
            partials=1,
        )
        head_report_totals = ReportTotals(
            coverage=85.0,
            files=1,
            lines=6,
            hits=3,
            misses=2,
            partials=1,
            diff=None,
        )
        patch_totals = ReportTotals(
            coverage=0.5,
            files=1,
            lines=2,
            hits=1,
            misses=1,
            partials=0,
        )

        TestImpactedFile = namedtuple(
            "TestImpactedFile",
            [
                "base_name",
                "head_name",
                "base_coverage",
                "head_coverage",
                "patch_coverage",
            ],
        )

        files_mock.return_value = [
            TestImpactedFile(
                base_name="foo.py",
                head_name="bar.py",
                base_coverage=base_report_totals,
                head_coverage=head_report_totals,
                patch_coverage=patch_totals,
            ),
            TestImpactedFile(
                base_name=None,
                head_name="baz.py",
                base_coverage=base_report_totals,
                head_coverage=head_report_totals,
                patch_coverage=patch_totals,
            ),
        ]
        critical_files.return_value = [
            CriticalFile("foo.py"),
        ]

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    impactedFiles(filters:{}) {
                        ... on ImpactedFiles {
                            results {
                                baseName
                                headName
                                isNewFile
                                isRenamedFile
                                isDeletedFile
                                baseCoverage {
                                    percentCovered
                                    fileCount
                                    lineCount
                                    hitsCount
                                    missesCount
                                    partialsCount
                                }
                                headCoverage {
                                    percentCovered
                                    fileCount
                                    lineCount
                                    hitsCount
                                    missesCount
                                    partialsCount
                                }
                                patchCoverage {
                                    percentCovered
                                    fileCount
                                    lineCount
                                    hitsCount
                                    missesCount
                                    partialsCount
                                }
                            }
                        }
                        ... on UnknownFlags {
                            message
                        }
                    }
                }
            }
        """

        base_totals = {
            "percentCovered": 75.0,
            "fileCount": 1,
            "lineCount": 6,
            "hitsCount": 3,
            "missesCount": 2,
            "partialsCount": 1,
        }
        head_totals = {
            "percentCovered": 85.0,
            "fileCount": 1,
            "lineCount": 6,
            "hitsCount": 3,
            "missesCount": 2,
            "partialsCount": 1,
        }
        patch_totals = {
            "percentCovered": 0.5,
            "fileCount": 1,
            "lineCount": 2,
            "hitsCount": 1,
            "missesCount": 1,
            "partialsCount": 0,
        }

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "impactedFiles": {
                    "results": [
                        {
                            "baseName": "foo.py",
                            "headName": "bar.py",
                            "isNewFile": False,
                            "isRenamedFile": True,
                            "isDeletedFile": False,
                            "baseCoverage": base_totals,
                            "headCoverage": head_totals,
                            "patchCoverage": patch_totals,
                        },
                        {
                            "baseName": None,
                            "headName": "baz.py",
                            "isNewFile": True,
                            "isRenamedFile": False,
                            "isDeletedFile": False,
                            "baseCoverage": base_totals,
                            "headCoverage": head_totals,
                            "patchCoverage": patch_totals,
                        },
                    ]
                },
            },
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch(
        "services.comparison.ComparisonReport.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_is_critical_file(self, files_mock, critical_files):
        TestImpactedFile = namedtuple("TestImpactedFile", ["base_name", "head_name"])

        files_mock.return_value = [
            TestImpactedFile(
                base_name="foo.py",
                head_name="bar.py",
            ),
            TestImpactedFile(
                base_name=None,
                head_name="baz.py",
            ),
        ]
        critical_files.return_value = [
            CriticalFile("foo.py"),
        ]

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    impactedFiles(filters:{}) {
                        ... on ImpactedFiles {
                            results {
                                baseName
                                headName
                                isCriticalFile
                            }
                        }
                        ... on UnknownFlags {
                            message
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "impactedFiles": {
                    "results": [
                        {
                            "baseName": "foo.py",
                            "headName": "bar.py",
                            "isCriticalFile": True,
                        },
                        {
                            "baseName": None,
                            "headName": "baz.py",
                            "isCriticalFile": False,
                        },
                    ]
                },
            },
        }

    @patch(
        "services.comparison.ComparisonReport.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_is_critical_file_returns_false_through_repositories(
        self, files_mock
    ):
        TestImpactedFile = namedtuple("TestImpactedFile", ["base_name", "head_name"])

        files_mock.return_value = [
            TestImpactedFile(
                base_name="foo.py",
                head_name="bar.py",
            ),
        ]

        query = """
            query {
                me {
                    owner {
                        repositories (first: 1) {
                            edges {
                                node {
                                    pull (id: %s) {
                                        pullId
                                        compareWithBase {
                                            ... on Comparison {
                                                impactedFiles(filters:{}) {
                                                    ... on ImpactedFiles {
                                                        results {
                                                            baseName
                                                            headName
                                                            isCriticalFile
                                                        }
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
                    }
                }
            }
        """

        data = self.gql_request(query % (self.pull.pullid), owner=self.owner)

        assert data == {
            "me": {
                "owner": {
                    "repositories": {
                        "edges": [
                            {
                                "node": {
                                    "pull": {
                                        "pullId": 2,
                                        "compareWithBase": {
                                            "impactedFiles": {
                                                "results": [
                                                    {
                                                        "baseName": "foo.py",
                                                        "headName": "bar.py",
                                                        "isCriticalFile": False,
                                                    }
                                                ]
                                            },
                                        },
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

    @patch(
        "services.comparison.PullRequestComparison.get_file_comparison",
    )
    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.ComparisonReport.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_line_comparisons(
        self, comparison_files_mock, files_mock, get_file_comparison
    ):
        TestFileComparison = namedtuple(
            "TestFileComparison",
            ["name", "head_name", "base_name", "has_diff", "has_changes", "segments"],
        )

        test_files = [
            TestFileComparison(
                name={"head": "file1", "base": "file1"},
                head_name="file1",
                base_name="file1",
                has_diff=True,
                has_changes=False,
                segments=[
                    MockSegmentComparison(
                        header=(1, 2, 3, 4),
                        has_unintended_changes=False,
                        lines=[
                            MockLineComparison(
                                number={
                                    "head": "1",
                                    "base": "1",
                                },
                                coverage={
                                    "base": LineType.hit,
                                    "head": LineType.hit,
                                },
                                value=" line1",
                                is_diff=False,
                                hit_session_ids=[0],
                            ),
                            MockLineComparison(
                                number={
                                    "base": None,
                                    "head": "2",
                                },
                                coverage={
                                    "base": None,
                                    "head": LineType.hit,
                                },
                                value="+ line2",
                                is_diff=True,
                                hit_session_ids=[0, 1],
                            ),
                        ],
                    ),
                ],
            ),
            TestFileComparison(
                name={"head": "file2", "base": "file2"},
                head_name="file2",
                base_name="file2",
                has_diff=False,
                has_changes=True,
                segments=[
                    MockSegmentComparison(
                        header=(1, None, 1, None),
                        has_unintended_changes=True,
                        lines=[
                            MockLineComparison(
                                number={
                                    "head": "1",
                                    "base": "1",
                                },
                                coverage={
                                    "base": LineType.miss,
                                    "head": LineType.hit,
                                },
                                value=" line1",
                                is_diff=True,
                                hit_session_ids=[0],
                            ),
                        ],
                    ),
                ],
            ),
        ]

        comparison_files_mock.return_value = test_files
        files_mock.return_value = test_files
        get_file_comparison.side_effect = test_files

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    impactedFiles(filters: {}){
                        ... on ImpactedFiles {
                            results {
                                segments {
                                    ... on SegmentComparisons {
                                        results {
                                            header
                                            hasUnintendedChanges
                                            lines {
                                                baseNumber
                                                headNumber
                                                baseCoverage
                                                headCoverage
                                                content
                                                coverageInfo(ignoredUploadIds: [1]) {
                                                    hitCount
                                                    hitUploadIds
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        ... on UnknownFlags {
                                message
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "impactedFiles": {
                    "results": [
                        {
                            "segments": {
                                "results": [
                                    {
                                        "header": "-1,2 +3,4",
                                        "hasUnintendedChanges": False,
                                        "lines": [
                                            {
                                                "baseNumber": "1",
                                                "headNumber": "1",
                                                "baseCoverage": "H",
                                                "headCoverage": "H",
                                                "content": "  line1",
                                                "coverageInfo": {
                                                    "hitCount": 1,
                                                    "hitUploadIds": [0],
                                                },
                                            },
                                            {
                                                "baseNumber": None,
                                                "headNumber": "2",
                                                "baseCoverage": None,
                                                "headCoverage": "H",
                                                "content": "+  line2",
                                                "coverageInfo": {
                                                    "hitCount": 1,
                                                    "hitUploadIds": [0],
                                                },
                                            },
                                        ],
                                    }
                                ]
                            }
                        },
                        {
                            "segments": {
                                "results": [
                                    {
                                        "header": "-1 +1",
                                        "hasUnintendedChanges": True,
                                        "lines": [
                                            {
                                                "baseNumber": "1",
                                                "headNumber": "1",
                                                "baseCoverage": "M",
                                                "headCoverage": "H",
                                                "content": "  line1",
                                                "coverageInfo": {
                                                    "hitCount": 1,
                                                    "hitUploadIds": [0],
                                                },
                                            }
                                        ],
                                    }
                                ]
                            }
                        },
                    ]
                },
            },
        }

    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.ComparisonReport.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_coverage_changes(
        self, comparison_files_mock, files_mock, get_file_comparison_mock
    ):
        TestFileComparison = namedtuple(
            "TestFileComparison",
            ["has_diff", "has_changes", "segments", "name", "head_name", "base_name"],
        )

        test_file_comparison = TestFileComparison(
            has_diff=False,
            has_changes=True,
            name={"head": "test", "base": "test"},
            head_name="test",
            base_name="test",
            segments=[
                MockSegmentComparison(
                    header=(1, 1, 1, 1),
                    has_unintended_changes=True,
                    lines=[
                        MockLineComparison(
                            number={
                                "head": "1",
                                "base": "1",
                            },
                            coverage={
                                "base": LineType.miss,
                                "head": LineType.hit,
                            },
                            value=" line1",
                            is_diff=True,
                            hit_session_ids=[0, 1],
                        ),
                    ],
                ),
            ],
        )

        get_file_comparison_mock.return_value = test_file_comparison

        comparison_files_mock.return_value = [test_file_comparison]
        files_mock.return_value = [test_file_comparison]

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    impactedFiles(filters: {}){
                        ... on ImpactedFiles {
                            results {
                                segments {
                                    ... on SegmentComparisons {
                                        results {
                                            header
                                            hasUnintendedChanges
                                            lines {
                                                baseNumber
                                                headNumber
                                                baseCoverage
                                                headCoverage
                                                content
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        ... on UnknownFlags {
                                message
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "impactedFiles": {
                    "results": [
                        {
                            "segments": {
                                "results": [
                                    {
                                        "header": "-1,1 +1,1",
                                        "hasUnintendedChanges": True,
                                        "lines": [
                                            {
                                                "baseNumber": "1",
                                                "headNumber": "1",
                                                "baseCoverage": "M",
                                                "headCoverage": "H",
                                                "content": "  line1",
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    ]
                },
            },
        }

    def test_pull_comparison_pending(self):
        self.commit_comparison.state = CommitComparison.CommitComparisonStates.PENDING
        self.commit_comparison.save()

        # these are created by default in the factory
        base_report = self.base_commit.reports.first()
        base_report.reportleveltotals.delete()
        head_report = self.head_commit.reports.first()
        head_report.reportleveltotals.delete()

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    state
                    baseTotals {
                        percentCovered
                    }
                    headTotals {
                        percentCovered
                    }
                    impactedFiles(filters: {}) {
                        ... on ImpactedFiles {
                            results {
                                baseName
                                headName
                            }
                        }
                        ... on UnknownFlags {
                                message
                        }
                    }
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "state": "pending",
                "baseTotals": None,
                "headTotals": None,
                "impactedFiles": {"results": []},
            },
        }

    @patch("services.task.TaskService.compute_comparisons")
    def test_pull_comparison_no_comparison(self, compute_comparisons_mock):
        self.commit_comparison.delete()

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    state
                }
            }
        """

        res = self._request(query)
        # it regenerates the comparison as needed
        assert res["compareWithBase"] is not None

        compute_comparisons_mock.assert_called_once

    def test_pull_comparison_missing_when_commit_comparison_state_is_errored(self):
        self.commit_comparison.state = CommitComparison.CommitComparisonStates.ERROR
        self.commit_comparison.save()

        query = """
            pullId
            compareWithBase {
                __typename
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {"__typename": "MissingComparison"},
        }

    def test_pull_comparison_missing_comparison(self):
        self.head_commit.delete()
        self.commit_comparison.delete()

        query = """
            pullId
            compareWithBase {
                __typename
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {"__typename": "MissingComparison"},
        }

    def test_pull_comparison_missing_base_sha(self):
        self.pull.compared_to = None
        self.pull.save()

        query = """
            pullId
            compareWithBase {
                __typename
                ... on ResolverError {
                    message
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "__typename": "MissingBaseCommit",
                "message": "Invalid base commit",
            },
        }

    def test_pull_comparison_missing_head_sha(self):
        self.pull.head = None
        self.pull.save()

        query = """
            pullId
            compareWithBase {
                __typename
                ... on ResolverError {
                    message
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "__typename": "MissingHeadCommit",
                "message": "Invalid head commit",
            },
        }

    def test_pull_comparison_missing_base_report(self):
        self.commit_comparison.error = "missing_base_report"
        self.commit_comparison.save()

        query = """
            pullId
            compareWithBase {
                __typename
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "__typename": "MissingBaseReport",
            },
        }

    def test_pull_comparison_missing_head_report(self):
        self.commit_comparison.error = "missing_head_report"
        self.commit_comparison.save()

        query = """
            pullId
            compareWithBase {
                __typename
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "__typename": "MissingHeadReport",
            },
        }

    @patch("services.task.TaskService.compute_comparisons")
    @patch("services.comparison.CommitComparisonService.needs_recompute")
    def test_pull_comparison_needs_recalculation(
        self, needs_recompute_mock, compute_comparisons_mock
    ):
        needs_recompute_mock.return_value = True

        query = """
            pullId
            compareWithBase {
                ... on Comparison {
                    state
                }
            }
        """

        res = self._request(query)
        # recalculates comparison
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {"state": "pending"},
        }
        compute_comparisons_mock.assert_called_once
