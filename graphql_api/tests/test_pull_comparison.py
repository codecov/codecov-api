from collections import namedtuple
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType

from codecov_auth.tests.factories import OwnerFactory
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


class TestPullComparison(TransactionTestCase, GraphQLTestHelper):
    def _request(self, query, pull):
        data = self.gql_request(
            base_query % (self.repository.name, pull.pullid, query), user=self.user
        )
        return data["me"]["owner"]["repository"]["pull"]

    def _create_pull(self, pullid):
        # FIXME: why is there a `pullid` collision when we create
        # this once in `setUp`?
        return PullFactory(
            pullid=pullid,
            repository=self.repository,
            author=self.user,
            head=self.head_commit.commitid,
            compared_to=self.base_commit.commitid,
        )

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

    @patch("services.comparison.Comparison.totals", new_callable=PropertyMock)
    def test_pull_comparison_totals(self, totals_mock):
        pull = self._create_pull(2)
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
            pullComparison {
                baseTotals {
                    coverage
                    fileCount
                    lineCount
                    hitsCount
                    missesCount
                    partialsCount
                }
                headTotals {
                    coverage
                    fileCount
                    lineCount
                    hitsCount
                    missesCount
                    partialsCount
                }
            }
        """

        res = self._request(query, pull)
        totals = {
            "coverage": 75.0,
            "fileCount": 1,
            "lineCount": 6,
            "hitsCount": 3,
            "missesCount": 2,
            "partialsCount": 1,
        }
        assert res == {
            "pullId": pull.pullid,
            "pullComparison": {
                "baseTotals": totals,
                "headTotals": totals,
            },
        }

    @patch("services.comparison.PullRequestComparison.files", new_callable=PropertyMock)
    def test_pull_comparison_file_comparisons(self, files_mock):
        pull = self._create_pull(3)

        report_totals = ReportTotals(
            coverage=75.0,
            files=1,
            lines=6,
            hits=3,
            misses=2,
            partials=1,
        )

        TestFileComparison = namedtuple(
            "TestFileComparison", ["name", "has_diff", "totals"]
        )
        files_mock.return_value = [
            TestFileComparison(
                name={
                    "base": "foo.py",
                    "head": "bar.py",
                },
                has_diff=True,
                totals={
                    "base": report_totals,
                    "head": report_totals,
                },
            ),
            TestFileComparison(
                name={
                    "base": None,
                    "head": "baz.py",
                },
                has_diff=True,
                totals={
                    "base": report_totals,
                    "head": report_totals,
                },
            ),
        ]

        query = """
            pullId
            pullComparison {
                fileComparisons {
                    baseName
                    headName
                    isNewFile
                    hasDiff
                    baseTotals {
                        coverage
                        fileCount
                        lineCount
                        hitsCount
                        missesCount
                        partialsCount
                    }
                    headTotals {
                        coverage
                        fileCount
                        lineCount
                        hitsCount
                        missesCount
                        partialsCount
                    }
                }
            }
        """

        totals = {
            "coverage": 75.0,
            "fileCount": 1,
            "lineCount": 6,
            "hitsCount": 3,
            "missesCount": 2,
            "partialsCount": 1,
        }

        res = self._request(query, pull)
        assert res == {
            "pullId": pull.pullid,
            "pullComparison": {
                "fileComparisons": [
                    {
                        "baseName": "foo.py",
                        "headName": "bar.py",
                        "isNewFile": False,
                        "hasDiff": True,
                        "baseTotals": totals,
                        "headTotals": totals,
                    },
                    {
                        "baseName": None,
                        "headName": "baz.py",
                        "isNewFile": True,
                        "hasDiff": True,
                        "baseTotals": totals,
                        "headTotals": totals,
                    },
                ]
            },
        }

    @patch("services.comparison.PullRequestComparison.files", new_callable=PropertyMock)
    def test_pull_comparison_line_comparisons(self, files_mock):
        pull = self._create_pull(4)

        TestFileComparison = namedtuple("TestFileComparison", ["lines"])
        TestLineComparison = namedtuple(
            "TestLineComparison", ["number", "coverage", "value"]
        )
        files_mock.return_value = [
            TestFileComparison(
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
                ]
            )
        ]

        query = """
            pullId
            pullComparison {
                fileComparisons {
                    lines {
                        baseNumber
                        headNumber
                        baseCoverage
                        headCoverage
                        content
                    }
                }
            }
        """

        res = self._request(query, pull)
        assert res == {
            "pullId": pull.pullid,
            "pullComparison": {
                "fileComparisons": [
                    {
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
                        ]
                    }
                ]
            },
        }
