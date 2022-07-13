from collections import namedtuple
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType

from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory, FlagComparisonFactory
from reports.tests.factories import RepositoryFlagFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

base_query = """{
    me {
        owner {
            repository(name: "%s") {
                pull(id: %s) {
                    %s
                }
            }
        }
    }
}
"""

TestSegmentComparison = namedtuple(
    "TestSegmentComparison", ["header", "lines", "has_unintended_changes"]
)
TestLineComparison = namedtuple("TestLineComparison", ["number", "coverage", "value"])


class TestPullComparison(TransactionTestCase, GraphQLTestHelper):
    def _request(self, query):
        data = self.gql_request(
            base_query % (self.repository.name, self.pull.pullid, query), user=self.user
        )
        return data["me"]["owner"]["repository"]["pull"]

    def setUp(self):
        self.user = OwnerFactory()
        self.repository = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
        )
        self.base_commit = CommitFactory(
            repository=self.repository,
            author=self.user,
        )
        self.head_commit = CommitFactory(
            parent_commit_id=self.base_commit.commitid,
            repository=self.repository,
            author=self.user,
        )
        self.commit_comparison = CommitComparisonFactory(
            base_commit=self.base_commit,
            compare_commit=self.head_commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )
        self.pull = PullFactory(
            pullid=2,
            repository=self.repository,
            author=self.user,
            head=self.head_commit.commitid,
            compared_to=self.base_commit.commitid,
        )

    @patch("services.comparison.Comparison.totals", new_callable=PropertyMock)
    def test_pull_comparison_totals(self, totals_mock):
        report_totals = ReportTotals(
            coverage=75.0,
            files=1,
            lines=6,
            hits=3,
            misses=2,
            partials=1,
        )
        totals_mock.return_value = {
            "base": report_totals,
            "head": report_totals,
        }

        query = """
            pullId
            compareWithBase {
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
        """

        res = self._request(query)
        assert res == {'compareWithBase': {'flagComparisons': []}}

    def test_pull_flag_comparisons(self):
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository,
                flag_name="flag_one"
            ),
            coverage_totals = {"coverage": "85.71429"},
            patch_totals = {"coverage": "29.28364"}
        )
        FlagComparisonFactory(
            commit_comparison=self.commit_comparison,
            repositoryflag=RepositoryFlagFactory(
                repository=self.repository,
                flag_name="flag_two"
            ),
            coverage_totals = {"coverage": "75.273820"},
            patch_totals = {"coverage": "68.283496"}
        )
        query = """
            compareWithBase {
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
        """

        res = self._request(query)
        assert res == {'compareWithBase': {'flagComparisons': [{'name': 'flag_one', 'patchTotals': {'percentCovered': 29.28364}, 'headTotals': {'percentCovered': 85.71429}}, {'name': 'flag_two', 'patchTotals': {'percentCovered': 68.283496}, 'headTotals': {'percentCovered': 75.27382}}]}}

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_file_comparisons(self, files_mock, critical_files):
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
            diff=ReportTotals(
                coverage=0.5,
                files=1,
                lines=2,
                hits=1,
                misses=1,
                partials=0,
            ),
        )

        TestFileComparison = namedtuple(
            "TestFileComparison", ["name", "has_diff", "has_changes", "totals"]
        )
        files_mock.return_value = [
            TestFileComparison(
                name={
                    "base": "foo.py",
                    "head": "bar.py",
                },
                has_diff=True,
                has_changes=False,
                totals={
                    "base": base_report_totals,
                    "head": head_report_totals,
                },
            ),
            TestFileComparison(
                name={
                    "base": None,
                    "head": "baz.py",
                },
                has_diff=True,
                has_changes=False,
                totals={
                    "base": base_report_totals,
                    "head": head_report_totals,
                },
            ),
        ]
        critical_files.return_value = [
            CriticalFile("foo.py"),
        ]

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    baseName
                    headName
                    isNewFile
                    isRenamedFile
                    isDeletedFile
                    hasDiff
                    hasChanges
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
                    patchTotals {
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
                "fileComparisons": [
                    {
                        "baseName": "foo.py",
                        "headName": "bar.py",
                        "isNewFile": False,
                        "isRenamedFile": True,
                        "isDeletedFile": False,
                        "hasDiff": True,
                        "hasChanges": False,
                        "baseTotals": base_totals,
                        "headTotals": head_totals,
                        "patchTotals": patch_totals,
                    },
                    {
                        "baseName": None,
                        "headName": "baz.py",
                        "isNewFile": True,
                        "isRenamedFile": False,
                        "isDeletedFile": False,
                        "hasDiff": True,
                        "hasChanges": False,
                        "baseTotals": base_totals,
                        "headTotals": head_totals,
                        "patchTotals": patch_totals,
                    },
                ]
            },
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_is_critical_file(self, files_mock, critical_files):

        TestFileComparisonIsCriticalFile = namedtuple(
            "TestFileComparisonIsCriticalFile", ["name", "has_diff", "has_changes"]
        )

        files_mock.return_value = [
            TestFileComparisonIsCriticalFile(
                name={
                    "base": "foo.py",
                    "head": "bar.py",
                },
                has_diff=True,
                has_changes=False,
            ),
            TestFileComparisonIsCriticalFile(
                name={
                    "base": None,
                    "head": "baz.py",
                },
                has_diff=True,
                has_changes=False,
            ),
        ]

        critical_files.return_value = [
            CriticalFile("foo.py"),
        ]

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    baseName
                    headName
                    isCriticalFile
                }
            }
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "fileComparisons": [
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
        }

    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_is_critical_file_returns_false_through_repositories(
        self, files_mock
    ):

        TestFileComparisonIsCriticalFile = namedtuple(
            "TestFileComparisonIsCriticalFile", ["name", "has_diff", "has_changes"]
        )

        files_mock.return_value = [
            TestFileComparisonIsCriticalFile(
                name={
                    "base": "foo.py",
                    "head": "bar.py",
                },
                has_diff=True,
                has_changes=False,
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
                                            fileComparisons {
                                                baseName
                                                headName
                                                isCriticalFile
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

        data = self.gql_request(query % (self.pull.pullid), user=self.user)

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
                                            "fileComparisons": [
                                                {
                                                    "baseName": "foo.py",
                                                    "headName": "bar.py",
                                                    "isCriticalFile": False,
                                                }
                                            ]
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
    def test_pull_comparison_line_comparisons(self, files_mock, get_file_comparison):
        TestFileComparison = namedtuple(
            "TestFileComparison", ["name", "has_diff", "has_changes", "segments"]
        )

        test_files = [
            TestFileComparison(
                name={"head": "file1", "base": "file1"},
                has_diff=True,
                has_changes=False,
                segments=[
                    TestSegmentComparison(
                        header=(1, 2, 3, 4),
                        has_unintended_changes=False,
                        lines=[
                            TestLineComparison(
                                number={
                                    "head": "1",
                                    "base": "1",
                                },
                                coverage={
                                    "base": LineType.hit,
                                    "head": LineType.hit,
                                },
                                value=" line1",
                            ),
                            TestLineComparison(
                                number={
                                    "base": None,
                                    "head": "2",
                                },
                                coverage={
                                    "base": None,
                                    "head": LineType.hit,
                                },
                                value="+ line2",
                            ),
                        ],
                    ),
                ],
            ),
            TestFileComparison(
                name={"head": "file2", "base": "file2"},
                has_diff=False,
                has_changes=True,
                segments=[
                    TestSegmentComparison(
                        header=(1, None, 1, None),
                        has_unintended_changes=True,
                        lines=[
                            TestLineComparison(
                                number={
                                    "head": "1",
                                    "base": "1",
                                },
                                coverage={
                                    "base": LineType.miss,
                                    "head": LineType.hit,
                                },
                                value=" line1",
                            ),
                        ],
                    ),
                ],
            ),
        ]

        files_mock.return_value = test_files
        get_file_comparison.side_effect = test_files

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    segments {
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
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "fileComparisons": [
                    {
                        "segments": [
                            {
                                "header": "-1,2 +3,4",
                                "hasUnintendedChanges": False,
                                "lines": [
                                    {
                                        "baseNumber": "1",
                                        "headNumber": "1",
                                        "baseCoverage": "H",
                                        "headCoverage": "H",
                                        "content": " line1",
                                    },
                                    {
                                        "baseNumber": None,
                                        "headNumber": "2",
                                        "baseCoverage": None,
                                        "headCoverage": "H",
                                        "content": "+ line2",
                                    },
                                ],
                            }
                        ]
                    },
                    {
                        "segments": [
                            {
                                "header": "-1 +1",
                                "hasUnintendedChanges": True,
                                "lines": [
                                    {
                                        "baseNumber": "1",
                                        "headNumber": "1",
                                        "baseCoverage": "M",
                                        "headCoverage": "H",
                                        "content": " line1",
                                    },
                                ],
                            }
                        ]
                    },
                ]
            },
        }

    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_coverage_changes(
        self, files_mock, get_file_comparison_mock
    ):
        TestFileComparison = namedtuple(
            "TestFileComparison", ["has_diff", "has_changes", "segments", "name"]
        )

        test_file_comparison = TestFileComparison(
            has_diff=False,
            has_changes=True,
            name={"head": "test", "base": "test"},
            segments=[
                TestSegmentComparison(
                    header=(1, 1, 1, 1),
                    has_unintended_changes=True,
                    lines=[
                        TestLineComparison(
                            number={
                                "head": "1",
                                "base": "1",
                            },
                            coverage={
                                "base": LineType.miss,
                                "head": LineType.hit,
                            },
                            value=" line1",
                        ),
                    ],
                ),
            ],
        )

        get_file_comparison_mock.return_value = test_file_comparison

        files_mock.return_value = [test_file_comparison]

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    segments {
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
        """

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "fileComparisons": [
                    {
                        "segments": [
                            {
                                "header": "-1,1 +1,1",
                                "hasUnintendedChanges": True,
                                "lines": [
                                    {
                                        "baseNumber": "1",
                                        "headNumber": "1",
                                        "baseCoverage": "M",
                                        "headCoverage": "H",
                                        "content": " line1",
                                    },
                                ],
                            }
                        ]
                    }
                ]
            },
        }

    def test_pull_comparison_pending(self):
        self.commit_comparison.state = CommitComparison.CommitComparisonStates.PENDING
        self.commit_comparison.save()

        query = """
            pullId
            compareWithBase {
                state
                baseTotals {
                    percentCovered
                }
                headTotals {
                    percentCovered
                }
                fileComparisons {
                    baseName
                    headName
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
                "fileComparisons": None,
            },
        }

    @patch("services.comparison.TaskService.compute_comparison")
    def test_pull_comparison_no_comparison(self, compute_comparison):
        self.commit_comparison.delete()

        query = """
            pullId
            compareWithBase {
                state
            }
        """

        res = self._request(query)
        # it regenerates the comparison as needed
        assert res["compareWithBase"] != None

    def test_pull_comparison_missing_commit(self):
        self.head_commit.delete()
        self.commit_comparison.delete()

        query = """
            pullId
            compareWithBase {
                state
            }
        """

        res = self._request(query)
        assert res == {"pullId": self.pull.pullid, "compareWithBase": None}

    def test_pull_comparison_missing_sha(self):
        self.pull.compared_to = None
        self.pull.save()

        query = """
            pullId
            compareWithBase {
                state
            }
        """

        res = self._request(query)
        assert res == {"pullId": self.pull.pullid, "compareWithBase": None}

    @patch("services.comparison.TaskService.compute_comparison")
    @patch("compare.models.CommitComparison.needs_recalculation", callable=PropertyMock)
    def test_pull_comparison_needs_recalculation(
        self, needs_recalculation, compute_comparison
    ):
        needs_recalculation.return_value = True

        query = """
            pullId
            compareWithBase {
                state
            }
        """

        res = self._request(query)
        # recalculates comparison
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {"state": "pending"},
        }
