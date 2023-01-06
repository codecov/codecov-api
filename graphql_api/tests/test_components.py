from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.reports.types import ReportTotals
from shared.utils.sessions import Session

from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from services.components import Component

from .helper import GraphQLTestHelper


def sample_report():
    report = Report()
    first_file = ReportFile("file_1.go")
    first_file.append(
        1, ReportLine.create(coverage=1, sessions=[[0, 1]], complexity=(10, 2))
    )
    first_file.append(2, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(3, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(5, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(6, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(8, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(9, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(10, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    second_file = ReportFile("file_2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


query_commit_components = """
    query CommitComponents(
        $org: String!
        $repo: String!
        $sha: String!
    ) {
        owner(username: $org) {
            repository(name: $repo) {
                commit(id: $sha) {
                    components {
                        id
                        name
                        totals {
                            hitsCount
                            missesCount
                            percentCovered
                        }
                    }
                }
            }
        }
    }
"""


class TestCommitComponents(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)

    def test_no_components(self):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
        }
        data = self.gql_request(query_commit_components, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "components": [],
                    }
                }
            }
        }

    @patch("core.models.Commit.full_report", new_callable=PropertyMock)
    @patch("services.components.commit_components")
    def test_components(self, commit_components_mock, full_report_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "python",
                    "paths": [".*/*.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "golang",
                    "paths": [".*/*.go"],
                }
            ),
        ]

        full_report_mock.return_value = sample_report()

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
        }
        data = self.gql_request(query_commit_components, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "components": [
                            {
                                "id": "python",
                                "name": "python",
                                "totals": {
                                    "hitsCount": 1,
                                    "missesCount": 0,
                                    "percentCovered": 50.0,
                                },
                            },
                            {
                                "id": "golang",
                                "name": "golang",
                                "totals": {
                                    "hitsCount": 5,
                                    "missesCount": 3,
                                    "percentCovered": 62.5,
                                },
                            },
                        ]
                    }
                }
            }
        }


query_components_comparison = """
    query ComponentsComparison(
        $org: String!
        $repo: String!
        $pullid: Int!
    ) {
        owner(username: $org) {
            repository(name: $repo) {
                pull(id: $pullid) {
                    compareWithBase {
                        __typename
                        ... on Comparison {
                            componentComparisons {
                                id
                                name
                                baseTotals {
                                    percentCovered
                                }
                                headTotals {
                                    percentCovered
                                }
                                patchTotals {
                                    percentCovered
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""


class TestComponentsComparison(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.base = CommitFactory(repository=self.repo)
        self.head = CommitFactory(
            repository=self.repo, parent_commit_id=self.base.commitid
        )
        self.pull = PullFactory(
            pullid=2,
            repository=self.repo,
            base=self.base.commitid,
            head=self.head.commitid,
            compared_to=self.base.commitid,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.base,
            compare_commit=self.head,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
        )

        # mock reports
        self.head_report_patcher = patch(
            "services.comparison.Comparison.head_report", new_callable=PropertyMock
        )
        self.head_report = self.head_report_patcher.start()
        self.head_report.return_value = sample_report()
        self.addCleanup(self.head_report_patcher.stop)
        self.base_report_patcher = patch(
            "services.comparison.Comparison.base_report", new_callable=PropertyMock
        )
        self.base_report = self.base_report_patcher.start()
        self.base_report.return_value = sample_report()
        self.addCleanup(self.base_report_patcher.stop)

    def test_no_components(self):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pullid": self.pull.pullid,
        }
        data = self.gql_request(query_components_comparison, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "__typename": "Comparison",
                            "componentComparisons": [],
                        }
                    }
                }
            }
        }

    @patch(
        "services.components.ComponentComparison.patch_totals",
        new_callable=PropertyMock,
    )
    @patch("services.components.commit_components")
    def test_components(self, commit_components_mock, patch_totals_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "python",
                    "paths": [".*/*.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "golang",
                    "paths": [".*/*.go"],
                }
            ),
        ]

        patch_totals_mock.return_value = ReportTotals(coverage=10)

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pullid": self.pull.pullid,
        }
        data = self.gql_request(query_components_comparison, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "__typename": "Comparison",
                            "componentComparisons": [
                                {
                                    "id": "python",
                                    "name": "python",
                                    "baseTotals": {"percentCovered": 50.0},
                                    "headTotals": {"percentCovered": 50.0},
                                    "patchTotals": {"percentCovered": 10.0},
                                },
                                {
                                    "id": "golang",
                                    "name": "golang",
                                    "baseTotals": {"percentCovered": 62.5},
                                    "headTotals": {"percentCovered": 62.5},
                                    "patchTotals": {"percentCovered": 10.0},
                                },
                            ],
                        }
                    }
                }
            }
        }

    def test_components_no_comparison(self):
        query = """
            query CommitComponentsComparison(
                $org: String!
                $repo: String!
                $sha: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        commit(id: $sha) {
                            compareWithParent {
                                componentComparisons {
                                    id
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
            "sha": self.head.commitid,
        }
        data = self.gql_request(query, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {"compareWithParent": {"componentComparisons": None}}
                }
            }
        }
