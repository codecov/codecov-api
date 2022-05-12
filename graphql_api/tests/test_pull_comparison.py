from collections import namedtuple
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType

from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory

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

TestSegmentComparison = namedtuple("TestSegmentComparison", ["header", "lines"])
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

    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_file_comparisons(self, files_mock):
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

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    baseName
                    headName
                    isNewFile
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

        res = self._request(query)
        assert res == {
            "pullId": self.pull.pullid,
            "compareWithBase": {
                "fileComparisons": [
                    {
                        "baseName": "foo.py",
                        "headName": "bar.py",
                        "isNewFile": False,
                        "hasDiff": True,
                        "hasChanges": False,
                        "baseTotals": base_totals,
                        "headTotals": head_totals,
                    },
                    {
                        "baseName": None,
                        "headName": "baz.py",
                        "isNewFile": True,
                        "hasDiff": True,
                        "hasChanges": False,
                        "baseTotals": base_totals,
                        "headTotals": head_totals,
                    },
                ]
            },
        }

    @patch(
        "services.comparison.PullRequestComparison.files",
        new_callable=PropertyMock,
    )
    def test_pull_comparison_line_comparisons(self, files_mock):
        TestFileComparison = namedtuple(
            "TestFileComparison", ["has_diff", "has_changes", "segments"]
        )

        files_mock.return_value = [
            TestFileComparison(
                has_diff=True,
                has_changes=False,
                segments=[
                    TestSegmentComparison(
                        header=[1, 2, 3, 4],
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
                has_diff=True,
                has_changes=False,
                segments=[
                    TestSegmentComparison(
                        header=[1, None, 1, None],
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

        query = """
            pullId
            compareWithBase {
                fileComparisons {
                    segments {
                        header
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
                                "lines": [
                                    {
                                        "baseNumber": "1",
                                        "headNumber": "1",
                                        "baseCoverage": "M",
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
                    header=None,
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
                                "header": None,
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

    @patch("compare.commands.compare.compare.CompareCommitsInteractor.execute")
    def test_pull_comparison_no_comparison(self, compare_mock):
        compare_mock.return_value = None

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
        assert res == {"pullId": self.pull.pullid, "compareWithBase": None}
