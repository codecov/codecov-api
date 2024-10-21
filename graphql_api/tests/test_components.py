from unittest.mock import PropertyMock, patch

import pytest
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory, ComponentComparisonFactory
from services.comparison import MissingComparisonReport
from services.components import Component
from timeseries.models import MeasurementName
from timeseries.tests.factories import DatasetFactory, MeasurementFactory

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
                ... on Repository {
                    commit(id: $sha) {
                        coverageAnalytics {
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
        }
    }
"""

query_repo = """
query Repo(
    $org: String!
    $repo: String!
    $sha: String!
) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                coverageAnalytics {
                    componentsMeasurementsActive
                    componentsMeasurementsBackfilled
                    componentsCount
                }
                commit(id: $sha) {
                    coverageAnalytics {
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
    }
}
"""

query_commit_coverage_components = """
    query CommitComponents(
        $org: String!
        $repo: String!
        $sha: String!
    ) {
        owner(username: $org) {
            repository(name: $repo) {
                ... on Repository {
                    commit(id: $sha) {
                        coverageAnalytics {
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
        }
    }
"""


class TestCommitCoverageComponents(GraphQLTestHelper, TransactionTestCase):
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
        data = self.gql_request(
            query_commit_coverage_components, variables=variables, owner=OwnerFactory()
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
                            "components": [],
                        }
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
        data = self.gql_request(
            query_commit_coverage_components,
            variables=variables,
            owner=OwnerFactory(),
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
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
        }

    @patch("core.models.Commit.full_report", new_callable=PropertyMock)
    @patch("services.components.commit_components")
    def test_components_filtering(self, commit_components_mock, full_report_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "python1.1",
                    "name": "Python",
                    "paths": [".*/*.py"],
                }
            ),
            Component.from_dict(
                {
                    "component_id": "golang1.2",
                    "name": "Golang",
                    "paths": [".*/*.go"],
                }
            ),
        ]

        full_report_mock.return_value = sample_report()

        query_commit_coverage_components = """
            query CommitComponents(
                $org: String!
                $repo: String!
                $sha: String!
                $filter: ComponentsFilters
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $sha) {
                                coverageAnalytics {
                                    components (filters: $filter) {
                                        id
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

        # Find one item
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
            "filter": {"components": ["Python"]},
        }
        data = self.gql_request(
            query_commit_coverage_components, variables=variables, owner=OwnerFactory()
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
                            "components": [
                                {
                                    "id": "python1.1",
                                    "name": "Python",
                                },
                            ]
                        }
                    }
                }
            }
        }

        # Find no items
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
            "filter": {"components": ["C++"]},
        }
        data = self.gql_request(query_commit_coverage_components, variables=variables)
        assert data == {
            "owner": {
                "repository": {"commit": {"coverageAnalytics": {"components": []}}}
            }
        }

        # Find all items
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
            "filter": {"components": []},
        }
        data = self.gql_request(query_commit_coverage_components, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
                            "components": [
                                {
                                    "id": "python1.1",
                                    "name": "Python",
                                },
                                {
                                    "id": "golang1.2",
                                    "name": "Golang",
                                },
                            ]
                        }
                    }
                }
            }
        }

        # Find some items
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "sha": self.commit.commitid,
            "filter": {"components": ["C", "Golang"]},
        }
        data = self.gql_request(
            query_commit_coverage_components, variables=variables, owner=OwnerFactory()
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
                            "components": [
                                {
                                    "id": "golang1.2",
                                    "name": "Golang",
                                },
                            ]
                        }
                    }
                }
            }
        }

    @patch("core.models.Commit.full_report", new_callable=PropertyMock)
    @patch("services.components.commit_components")
    def test_components_filtering_case_insensitive(
        self, commit_components_mock, full_report_mock
    ):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "cpython",
                    "name": "PyThOn",
                    "paths": [".*/*.py"],
                }
            ),
        ]

        full_report_mock.return_value = sample_report()

        query_commit_coverage_components = """
            query CommitComponents(
                $org: String!
                $repo: String!
                $sha: String!
                $filter: ComponentsFilters
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $sha) {
                                coverageAnalytics {
                                    components (filters: $filter) {
                                        id
                                        name
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
            "sha": self.commit.commitid,
            "filter": {"components": ["pYtHoN"]},
        }
        data = self.gql_request(
            query_commit_coverage_components, variables=variables, owner=OwnerFactory()
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "coverageAnalytics": {
                            "components": [
                                {
                                    "id": "cpython",
                                    "name": "PyThOn",
                                },
                            ]
                        }
                    }
                }
            }
        }


query_components_comparison = """
    query ComponentsComparison(
        $org: String!
        $repo: String!
        $pullid: Int!
        $filters: ComponentsFilters
    ) {
        owner(username: $org) {
            repository(name: $repo) {
                ... on Repository {
                    pull(id: $pullid) {
                        compareWithBase {
                            __typename
                            ... on Comparison {
                                componentComparisonsCount
                                componentComparisons(filters: $filters) {
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
    }
"""


class TestComponentsComparison(GraphQLTestHelper, TransactionTestCase):
    databases = {"default", "timeseries"}

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
        self.commit = CommitFactory(repository=self.repo)

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

    def test_no_components_in_pull_request(self):
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
                            "componentComparisonsCount": 0,
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    def test_components_invalid_comparison_object(self, mock_compare_validate):
        mock_compare_validate.side_effect = MissingComparisonReport()
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
                            "componentComparisonsCount": 0,
                        }
                    }
                }
            }
        }

    @patch("services.components.commit_components")
    def test_components(self, commit_components_mock):
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

        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="python",
        )
        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="golang",
        )

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
                            "componentComparisonsCount": 2,
                            "componentComparisons": [
                                {
                                    "id": "python",
                                    "name": "python",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                                {
                                    "id": "golang",
                                    "name": "golang",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                            ],
                        }
                    }
                }
            }
        }

    @patch("services.components.commit_components")
    def test_components_filter(self, commit_components_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {"component_id": "python", "paths": [".*/*.py"], "name": "python"}
            ),
            Component.from_dict(
                {"component_id": "golang", "paths": [".*/*.go"], "name": "golang"}
            ),
        ]

        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="python",
        )
        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="golang",
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pullid": self.pull.pullid,
            "filters": {"components": ["python"]},
        }
        data = self.gql_request(query_components_comparison, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "__typename": "Comparison",
                            "componentComparisonsCount": 2,
                            "componentComparisons": [
                                {
                                    "id": "python",
                                    "name": "python",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                            ],
                        }
                    }
                }
            }
        }

    @patch("services.components.commit_components")
    def test_components_multi_filter(self, commit_components_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {"component_id": "python", "paths": [".*/*.py"], "name": "python"}
            ),
            Component.from_dict(
                {"component_id": "golang", "paths": [".*/*.go"], "name": "golang"}
            ),
            Component.from_dict(
                {"component_id": "js", "paths": [".*/*.js"], "name": "javascript"}
            ),
        ]

        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="python",
        )
        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="golang",
        )
        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="js",
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pullid": self.pull.pullid,
            "filters": {"components": ["python", "javascript"]},
        }
        data = self.gql_request(query_components_comparison, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "__typename": "Comparison",
                            "componentComparisonsCount": 3,
                            "componentComparisons": [
                                {
                                    "id": "python",
                                    "name": "python",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                                {
                                    "id": "js",
                                    "name": "javascript",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                            ],
                        }
                    }
                }
            }
        }

    @patch("services.components.commit_components")
    def test_components_filter_case_insensitive(self, commit_components_mock):
        commit_components_mock.return_value = [
            Component.from_dict(
                {"component_id": "python1.1", "paths": [".*/*.py"], "name": "PYThon"}
            ),
            Component.from_dict(
                {"component_id": "golang1.2", "paths": [".*/*.go"], "name": "GOLang"}
            ),
        ]

        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="python1.1",
        )
        ComponentComparisonFactory(
            commit_comparison=self.comparison,
            component_id="golang1.2",
        )

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pullid": self.pull.pullid,
            "filters": {"components": ["PYThon", "golANG"]},
        }
        data = self.gql_request(query_components_comparison, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "__typename": "Comparison",
                            "componentComparisonsCount": 2,
                            "componentComparisons": [
                                {
                                    "id": "python1.1",
                                    "name": "PYThon",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                                {
                                    "id": "golang1.2",
                                    "name": "GOLang",
                                    "baseTotals": {"percentCovered": 72.92638},
                                    "headTotals": {"percentCovered": 85.71429},
                                    "patchTotals": {"percentCovered": 28.57143},
                                },
                            ],
                        }
                    }
                }
            }
        }

    def test_repository_components_metadata_inactive(self):
        data = self.gql_request(
            query_repo,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "sha": self.commit.commitid,
            },
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsActive"
            ]
            == False
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsBackfilled"
            ]
            == False
        )

    def test_repository_components_metadata_active(self):
        DatasetFactory(
            name=MeasurementName.COMPONENT_COVERAGE.value,
            repository_id=self.repo.pk,
        )

        data = self.gql_request(
            query_repo,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "sha": self.commit.commitid,
            },
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsActive"
            ]
            == True
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsBackfilled"
            ]
            == False
        )

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_repository_components_metadata_backfilled_true(self, is_backfilled):
        is_backfilled.return_value = True

        DatasetFactory(
            name=MeasurementName.COMPONENT_COVERAGE.value,
            repository_id=self.repo.pk,
        )

        data = self.gql_request(
            query_repo,
            variables={
                "org": self.org.username,
                "repo": self.repo.name,
                "sha": self.commit.commitid,
            },
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsActive"
            ]
            == True
        )
        assert (
            data["owner"]["repository"]["coverageAnalytics"][
                "componentsMeasurementsBackfilled"
            ]
            == True
        )


query_component_measurements = """
query ComponentMeasurements(
    $name: String!
    $repo: String!
    $interval: MeasurementInterval!
    $after: DateTime!
    $before: DateTime!
    $branch: String
    $filters: ComponentMeasurementsSetFilters
    $orderingDirection: OrderingDirection
) {
    owner(username: $name) {
        repository(name: $repo) {
            ... on Repository {
                coverageAnalytics {
                    components(filters: $filters, orderingDirection: $orderingDirection, after: $after, before: $before, branch: $branch, interval: $interval) {
                        __typename
                        ... on ComponentMeasurements {
                            name
                            percentCovered
                            percentChange
                            measurements {
                                avg
                                min
                                max
                                timestamp
                            }
                            lastUploaded
                        }
                    }
                }
            }
        }
    }
}
"""


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class TestComponentMeasurements(GraphQLTestHelper, TransactionTestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(
            author=self.org,
            private=False,
            yaml={
                "component_management": {
                    "default_rules": {},
                    "individual_components": [
                        {
                            "component_id": "python",
                            "name": "pythonName",
                            "paths": [".*/*.py"],
                        },
                        {
                            "component_id": "golang",
                            "paths": [".*/*.go"],
                        },
                    ],
                }
            },
        )
        self.commit = CommitFactory(repository=self.repo)

    def test_component_measurements_with_measurements(self):
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=95.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )

        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
        }
        data = self.gql_request(query_component_measurements, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "coverageAnalytics": {
                        "components": [
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "golang",
                                "percentCovered": 90.0,
                                "percentChange": 5.0,
                                "measurements": [
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-20T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 85.0,
                                        "min": 85.0,
                                        "max": 85.0,
                                        "timestamp": "2022-06-21T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 90.0,
                                        "min": 85.0,
                                        "max": 95.0,
                                        "timestamp": "2022-06-22T00:00:00+00:00",
                                    },
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-23T00:00:00+00:00",
                                    },
                                ],
                                "lastUploaded": "2022-06-22T01:00:00+00:00",
                            },
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "pythonName",
                                "percentCovered": 80.0,
                                "percentChange": 5.0,
                                "measurements": [
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-20T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 75.0,
                                        "min": 75.0,
                                        "max": 75.0,
                                        "timestamp": "2022-06-21T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 80.0,
                                        "min": 75.0,
                                        "max": 85.0,
                                        "timestamp": "2022-06-22T00:00:00+00:00",
                                    },
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-23T00:00:00+00:00",
                                    },
                                ],
                                "lastUploaded": "2022-06-22T01:00:00+00:00",
                            },
                        ]
                    }
                }
            }
        }

    def test_component_measurements_no_measurements(self):
        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
        }
        data = self.gql_request(query_component_measurements, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "coverageAnalytics": {
                        "components": [
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "golang",
                                "percentCovered": None,
                                "percentChange": None,
                                "measurements": [],
                                "lastUploaded": None,
                            },
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "pythonName",
                                "percentCovered": None,
                                "percentChange": None,
                                "measurements": [],
                                "lastUploaded": None,
                            },
                        ]
                    }
                }
            }
        }

    @override_settings(TIMESERIES_ENABLED=False)
    def test_component_measurements_timeseries_not_enabled(self):
        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
        }
        data = self.gql_request(query_component_measurements, variables=variables)
        assert data == {
            "owner": {"repository": {"coverageAnalytics": {"components": []}}}
        }

    def test_component_measurements_with_filter(self):
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=95.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )

        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
            "filters": {"components": ["python"]},
        }
        data = self.gql_request(query_component_measurements, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "coverageAnalytics": {
                        "components": [
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "pythonName",
                                "percentCovered": 80.0,
                                "percentChange": 5.0,
                                "measurements": [
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-20T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 75.0,
                                        "min": 75.0,
                                        "max": 75.0,
                                        "timestamp": "2022-06-21T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 80.0,
                                        "min": 75.0,
                                        "max": 85.0,
                                        "timestamp": "2022-06-22T00:00:00+00:00",
                                    },
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-23T00:00:00+00:00",
                                    },
                                ],
                                "lastUploaded": "2022-06-22T01:00:00+00:00",
                            },
                        ]
                    }
                }
            }
        }

    def test_component_measurements_with_branch(self):
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=95.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )

        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
            "branch": "dev",
        }
        data = self.gql_request(query_component_measurements, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "coverageAnalytics": {
                        "components": [
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "golang",
                                "percentCovered": 90.0,
                                "percentChange": 5.0,
                                "measurements": [
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-20T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 85.0,
                                        "min": 85.0,
                                        "max": 85.0,
                                        "timestamp": "2022-06-21T00:00:00+00:00",
                                    },
                                    {
                                        "avg": 90.0,
                                        "min": 85.0,
                                        "max": 95.0,
                                        "timestamp": "2022-06-22T00:00:00+00:00",
                                    },
                                    {
                                        "avg": None,
                                        "min": None,
                                        "max": None,
                                        "timestamp": "2022-06-23T00:00:00+00:00",
                                    },
                                ],
                                "lastUploaded": "2022-06-22T01:00:00+00:00",
                            },
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "pythonName",
                                "percentCovered": None,
                                "percentChange": None,
                                "measurements": [],
                                "lastUploaded": None,
                            },
                        ]
                    }
                }
            }
        }

    def test_component_measurements_id_fallback(self):
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="main",
            measurable_id="python",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=95.0,
        )
        MeasurementFactory(
            name="component_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="dev",
            measurable_id="golang",
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )

        query = """
           query ComponentMeasurements(
               $name: String!
               $repo: String!
               $interval: MeasurementInterval!
               $after: DateTime!
               $before: DateTime!
               $branch: String
               $filters: ComponentMeasurementsSetFilters
               $orderingDirection: OrderingDirection
           ) {
               owner(username: $name) {
                   repository: repository(name: $repo) {
                       ... on Repository {
                            coverageAnalytics {
                               components(filters: $filters, orderingDirection: $orderingDirection, after: $after, before: $before, branch: $branch, interval: $interval) {
                                   __typename
                                   ... on ComponentMeasurements {
                                       name
                                       componentId
                                   }
                               }
                           }
                       }
                   }
               }
           }
           """

        variables = {
            "name": self.org.username,
            "repo": self.repo.name,
            "interval": "INTERVAL_1_DAY",
            "after": timezone.datetime(2022, 6, 20),
            "before": timezone.datetime(2022, 6, 23),
            "branch": "dev",
        }
        data = self.gql_request(query, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "coverageAnalytics": {
                        "components": [
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "golang",
                                "componentId": "golang",
                            },
                            {
                                "__typename": "ComponentMeasurements",
                                "name": "pythonName",
                                "componentId": "python",
                            },
                        ]
                    }
                }
            }
        }
