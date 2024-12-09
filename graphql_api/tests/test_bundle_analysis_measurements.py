from unittest.mock import patch

from django.test import TransactionTestCase
from shared.api_archive.archive import ArchiveService
from shared.bundle_analysis import StoragePaths
from shared.bundle_analysis.storage import get_bucket_name
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.storage.memory import MemoryStorageService

from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory
from timeseries.tests.factories import MeasurementFactory

from .helper import GraphQLTestHelper


class TestBundleAnalysisMeasurements(GraphQLTestHelper, TransactionTestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.parent_commit = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(
            repository=self.repo,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=self.parent_commit.commitid,
        )
        self.head_commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        measurements_data = [
            # 2024-06-10
            ["bundle_analysis_report_size", "super", "2024-06-10T19:07:22", 29927],
            ["bundle_analysis_font_size", "super", "2024-06-10T19:07:22", 290],
            ["bundle_analysis_image_size", "super", "2024-06-10T19:07:22", 2900],
            ["bundle_analysis_stylesheet_size", "super", "2024-06-10T19:07:22", 29],
            ["bundle_analysis_javascript_size", "super", "2024-06-10T19:07:22", 26708],
            [
                "bundle_analysis_asset_size",
                "ca05c27a-74f7-4d0e-a851-537c7b2bcb48",
                "2024-06-10T19:07:22",
                14126,
            ],
            [
                "bundle_analysis_asset_size",
                "4e03bec3-1af3-4e58-b1b7-99aa995122a6",
                "2024-06-10T19:07:22",
                11421,
            ],
            # 2024-06-06
            ["bundle_analysis_report_size", "super", "2024-06-06T19:07:22", 6263],
            ["bundle_analysis_font_size", "super", "2024-06-06T19:07:22", 50],
            ["bundle_analysis_image_size", "super", "2024-06-06T19:07:22", 500],
            ["bundle_analysis_stylesheet_size", "super", "2024-06-06T19:07:22", 5],
            ["bundle_analysis_javascript_size", "super", "2024-06-06T19:07:22", 5708],
            [
                "bundle_analysis_asset_size",
                "ca05c27a-74f7-4d0e-a851-537c7b2bcb48",
                "2024-06-06T19:07:22",
                4126,
            ],
            [
                "bundle_analysis_asset_size",
                "4e03bec3-1af3-4e58-b1b7-99aa995122a6",
                "2024-06-06T19:07:22",
                1421,
            ],
        ]

        for item in measurements_data:
            MeasurementFactory(
                name=item[0],
                owner_id=self.org.pk,
                repo_id=self.repo.pk,
                branch="main",
                measurable_id=item[1],
                commit_sha=self.commit.pk,
                timestamp=item[2],
                value=item[3],
            )

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_measurements(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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

        # Test without using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-06",
            "before": "2024-06-10",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 4126.0,
                                "max": 4126.0,
                                "min": 4126.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 14126.0,
                                "max": 14126.0,
                                "min": 14126.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 150,
                            },
                            "size": {
                                "gzip": 14,
                                "uncompress": 14126,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 1421.0,
                                "max": 1421.0,
                                "min": 1421.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 11421.0,
                                "max": 11421.0,
                                "min": 11421.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 121,
                            },
                            "size": {
                                "gzip": 11,
                                "uncompress": 11421,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 2,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 240,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 50.0,
                                "max": 50.0,
                                "min": 50.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 290.0,
                                "max": 290.0,
                                "min": 290.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 3,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 290,
                            },
                        },
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 25,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2400,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 500.0,
                                "max": 500.0,
                                "min": 500.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 2900.0,
                                "max": 2900.0,
                                "min": 2900.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 30,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2900,
                            },
                        },
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 6,
                                "threeG": 252,
                            },
                            "size": {
                                "gzip": 23,
                                "uncompress": 23664,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 6263.0,
                                "max": 6263.0,
                                "min": 6263.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29927.0,
                                "max": 29927.0,
                                "min": 29927.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 319,
                            },
                            "size": {
                                "gzip": 29,
                                "uncompress": 29927,
                            },
                        },
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 24,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5.0,
                                "max": 5.0,
                                "min": 5.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29.0,
                                "max": 29.0,
                                "min": 29.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 29,
                            },
                        },
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

        # Test with using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-06",
            "before": "2024-06-10",
            "filters": {"assetTypes": "JAVASCRIPT_SIZE"},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_asset_measurements(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
                $asset: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                asset(name: $asset){
                                                    name
                                                    measurements(
                                                        after: $after
                                                        interval: $interval
                                                        before: $before
                                                    ){
                                                        assetType
                                                        name
                                                        size {
                                                            loadTime {
                                                                threeG
                                                                highSpeed
                                                            }
                                                            size {
                                                                gzip
                                                                uncompress
                                                            }
                                                        }
                                                        change {
                                                            loadTime {
                                                                threeG
                                                                highSpeed
                                                            }
                                                            size {
                                                                gzip
                                                                uncompress
                                                            }
                                                        }
                                                        measurements {
                                                            avg
                                                            min
                                                            max
                                                            timestamp
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

        # Tests can only fetch JS asset
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-06",
            "before": "2024-06-10",
            "asset": "asset-same-name-diff-modules.js",
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "asset": {
                    "measurements": {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 4126.0,
                                "max": 4126.0,
                                "min": 4126.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 14126.0,
                                "max": 14126.0,
                                "min": 14126.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 150,
                            },
                            "size": {
                                "gzip": 14,
                                "uncompress": 14126,
                            },
                        },
                    },
                    "name": "asset-same-name-diff-modules.js",
                },
            },
        }

        # Tests non-JS asset can't be fetched
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-06",
            "before": "2024-06-10",
            "asset": "asset-css-A-TWO.css",
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "asset": {
                    "measurements": None,
                    "name": "asset-css-A-TWO.css",
                },
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_measurements_carryovers(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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

        # Test without using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-07",
            "before": "2024-06-10",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 4126.0,
                                "max": 4126.0,
                                "min": 4126.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 14126.0,
                                "max": 14126.0,
                                "min": 14126.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 150,
                            },
                            "size": {
                                "gzip": 14,
                                "uncompress": 14126,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 1421.0,
                                "max": 1421.0,
                                "min": 1421.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 11421.0,
                                "max": 11421.0,
                                "min": 11421.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 121,
                            },
                            "size": {
                                "gzip": 11,
                                "uncompress": 11421,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 2,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 240,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 50.0,
                                "max": 50.0,
                                "min": 50.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 290.0,
                                "max": 290.0,
                                "min": 290.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 3,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 290,
                            },
                        },
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 25,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2400,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 500.0,
                                "max": 500.0,
                                "min": 500.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 2900.0,
                                "max": 2900.0,
                                "min": 2900.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 30,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2900,
                            },
                        },
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 6,
                                "threeG": 252,
                            },
                            "size": {
                                "gzip": 23,
                                "uncompress": 23664,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 6263.0,
                                "max": 6263.0,
                                "min": 6263.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29927.0,
                                "max": 29927.0,
                                "min": 29927.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 319,
                            },
                            "size": {
                                "gzip": 29,
                                "uncompress": 29927,
                            },
                        },
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 24,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5.0,
                                "max": 5.0,
                                "min": 5.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29.0,
                                "max": 29.0,
                                "min": 29.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 29,
                            },
                        },
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

        # Test with using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-07",
            "before": "2024-06-10",
            "filters": {"assetTypes": "JAVASCRIPT_SIZE"},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_no_carryovers(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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

        # Test without using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-05",
            "before": "2024-06-10",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 4126.0,
                                "max": 4126.0,
                                "min": 4126.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 14126.0,
                                "max": 14126.0,
                                "min": 14126.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 150,
                            },
                            "size": {
                                "gzip": 14,
                                "uncompress": 14126,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 2,
                                "threeG": 106,
                            },
                            "size": {
                                "gzip": 10,
                                "uncompress": 10000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 1421.0,
                                "max": 1421.0,
                                "min": 1421.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 11421.0,
                                "max": 11421.0,
                                "min": 11421.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": "asset-*.js",
                        "size": {
                            "loadTime": {
                                "highSpeed": 3,
                                "threeG": 121,
                            },
                            "size": {
                                "gzip": 11,
                                "uncompress": 11421,
                            },
                        },
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 2,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 240,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 50.0,
                                "max": 50.0,
                                "min": 50.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 290.0,
                                "max": 290.0,
                                "min": 290.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 3,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 290,
                            },
                        },
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 25,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2400,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 500.0,
                                "max": 500.0,
                                "min": 500.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 2900.0,
                                "max": 2900.0,
                                "min": 2900.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 30,
                            },
                            "size": {
                                "gzip": 2,
                                "uncompress": 2900,
                            },
                        },
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 6,
                                "threeG": 252,
                            },
                            "size": {
                                "gzip": 23,
                                "uncompress": 23664,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 6263.0,
                                "max": 6263.0,
                                "min": 6263.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29927.0,
                                "max": 29927.0,
                                "min": 29927.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 319,
                            },
                            "size": {
                                "gzip": 29,
                                "uncompress": 29927,
                            },
                        },
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 24,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 5.0,
                                "max": 5.0,
                                "min": 5.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 29.0,
                                "max": 29.0,
                                "min": 29.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 29,
                            },
                        },
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

        # Test with using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-05",
            "before": "2024-06-10",
            "filters": {"assetTypes": "JAVASCRIPT_SIZE"},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 5,
                                "threeG": 224,
                            },
                            "size": {
                                "gzip": 21,
                                "uncompress": 21000,
                            },
                        },
                        "measurements": [
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 5708.0,
                                "max": 5708.0,
                                "min": 5708.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 26708.0,
                                "max": 26708.0,
                                "min": 26708.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 7,
                                "threeG": 284,
                            },
                            "size": {
                                "gzip": 26,
                                "uncompress": 26708,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_branch(self, get_storage_service):
        measurements_data = [
            # 2024-06-10
            ["bundle_analysis_report_size", "super", "2024-06-10T19:07:23", 123],
            # 2024-06-06
            ["bundle_analysis_report_size", "super", "2024-06-06T19:07:23", 456],
        ]

        for item in measurements_data:
            MeasurementFactory(
                name=item[0],
                owner_id=self.org.pk,
                repo_id=self.repo.pk,
                branch="feat",
                measurable_id=item[1],
                commit_sha=self.commit.pk,
                timestamp=item[2],
                value=item[3],
            )

        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
                $branch: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                    branch: $branch
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-07",
            "before": "2024-06-10",
            "branch": "feat",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "name": "super",
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "name": None,
                        "size": {
                            "loadTime": {"threeG": 1, "highSpeed": 0},
                            "size": {"gzip": 0, "uncompress": 123},
                        },
                        "change": {
                            "loadTime": {"threeG": -3, "highSpeed": 0},
                            "size": {"gzip": 0, "uncompress": -333},
                        },
                        "measurements": [
                            {
                                "avg": 456.0,
                                "min": 456.0,
                                "max": 456.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "min": None,
                                "max": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "min": None,
                                "max": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 123.0,
                                "min": 123.0,
                                "max": 123.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": -3,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": -333,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 456.0,
                                "max": 456.0,
                                "min": 456.0,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 123.0,
                                "max": 123.0,
                                "min": 123.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 1,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 123,
                            },
                        },
                    },
                ],
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_no_after(self, get_storage_service):
        measurements_data = [
            # 2024-06-10
            ["bundle_analysis_report_size", "super", "2024-06-10T19:07:23", 123],
            # 2024-06-06
            ["bundle_analysis_report_size", "super", "2024-06-06T19:07:23", 456],
        ]

        for item in measurements_data:
            MeasurementFactory(
                name=item[0],
                owner_id=self.org.pk,
                repo_id=self.repo.pk,
                branch="feat",
                measurable_id=item[1],
                commit_sha=self.commit.pk,
                timestamp=item[2],
                value=item[3],
            )

        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime
                $branch: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                    branch: $branch
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": None,
            "before": "2024-06-10",
            "branch": "feat",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "name": "super",
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "name": "asset-*.js",
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "name": None,
                        "size": {
                            "loadTime": {"threeG": 1, "highSpeed": 0},
                            "size": {"gzip": 0, "uncompress": 123},
                        },
                        "change": {
                            "loadTime": {"threeG": -3, "highSpeed": 0},
                            "size": {"gzip": 0, "uncompress": -333},
                        },
                        "measurements": [
                            {
                                "avg": 456.0,
                                "min": 456.0,
                                "max": 456.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "min": None,
                                "max": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "min": None,
                                "max": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "min": None,
                                "max": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 123.0,
                                "min": 123.0,
                                "max": 123.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "name": None,
                        "size": None,
                        "change": None,
                        "measurements": [],
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": -3,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": -333,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 456.0,
                                "max": 456.0,
                                "min": 456.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 123.0,
                                "max": 123.0,
                                "min": 123.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 1,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 123,
                            },
                        },
                    },
                ],
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_bad_data_check(self, get_storage_service):
        measurements_data = [
            # 2024-06-10
            ["bundle_analysis_report_size", "super", "2024-06-10T19:07:23", 123],
            # 2024-06-06
            ["bundle_analysis_image_size", "super", "2024-06-06T19:07:23", 456],
            # 2024-06-05
            ["bundle_analysis_image_size", "super", "2024-06-05T19:07:23", 666],
        ]

        for item in measurements_data:
            MeasurementFactory(
                name=item[0],
                owner_id=self.org.pk,
                repo_id=self.repo.pk,
                branch="feat",
                measurable_id=item[1],
                commit_sha=self.commit.pk,
                timestamp=item[2],
                value=item[3],
            )

        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime
                $branch: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                    branch: $branch
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": None,
            "before": "2024-06-10",
            "branch": "feat",
            "filters": {},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "ASSET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": "asset-*.js",
                        "size": None,
                    },
                    {
                        "assetType": "FONT_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": None,
                        "size": None,
                    },
                    {
                        "assetType": "IMAGE_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": -2,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": -210,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 666.0,
                                "max": 666.0,
                                "min": 666.0,
                                "timestamp": "2024-06-05T00:00:00+00:00",
                            },
                            {
                                "avg": 456.0,
                                "max": 456.0,
                                "min": 456.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 4,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 456,
                            },
                        },
                    },
                    {
                        "assetType": "JAVASCRIPT_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": None,
                        "size": None,
                    },
                    {
                        "assetType": "REPORT_SIZE",
                        "change": None,
                        "measurements": [
                            {
                                "avg": 123.0,
                                "max": 123.0,
                                "min": 123.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 1,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 123,
                            },
                        },
                    },
                    {
                        "assetType": "STYLESHEET_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": None,
                        "size": None,
                    },
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": None,
                        "measurements": [],
                        "name": None,
                        "size": None,
                    },
                ],
                "name": "super",
            },
        }

    @patch("graphql_api.dataloader.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_report_measurements_only_unknown(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/bundle_with_uuid.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        query = """
            query FetchMeasurements(
                $org: String!,
                $repo: String!,
                $commit: String!
                $filters: BundleAnalysisMeasurementsSetFilters
                $orderingDirection: OrderingDirection!
                $interval: MeasurementInterval!
                $before: DateTime!
                $after: DateTime!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                bundleAnalysis {
                                    bundleAnalysisReport {
                                        __typename
                                        ... on BundleAnalysisReport {
                                            bundle(name: "super") {
                                                name
                                                measurements(
                                                    filters: $filters
                                                    orderingDirection: $orderingDirection
                                                    after: $after
                                                    interval: $interval
                                                    before: $before
                                                ){
                                                    assetType
                                                    name
                                                    size {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    change {
                                                        loadTime {
                                                            threeG
                                                            highSpeed
                                                        }
                                                        size {
                                                            gzip
                                                            uncompress
                                                        }
                                                    }
                                                    measurements {
                                                        avg
                                                        min
                                                        max
                                                        timestamp
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

        # Test without using asset type filters
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "orderingDirection": "ASC",
            "interval": "INTERVAL_1_DAY",
            "after": "2024-06-06",
            "before": "2024-06-10",
            "filters": {"assetTypes": ["UNKNOWN_SIZE"]},
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]

        assert commit["bundleAnalysis"]["bundleAnalysisReport"] == {
            "__typename": "BundleAnalysisReport",
            "bundle": {
                "measurements": [
                    {
                        "assetType": "UNKNOWN_SIZE",
                        "change": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                        "measurements": [
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-06T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-07T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-08T00:00:00+00:00",
                            },
                            {
                                "avg": None,
                                "max": None,
                                "min": None,
                                "timestamp": "2024-06-09T00:00:00+00:00",
                            },
                            {
                                "avg": 0.0,
                                "max": 0.0,
                                "min": 0.0,
                                "timestamp": "2024-06-10T00:00:00+00:00",
                            },
                        ],
                        "name": None,
                        "size": {
                            "loadTime": {
                                "highSpeed": 0,
                                "threeG": 0,
                            },
                            "size": {
                                "gzip": 0,
                                "uncompress": 0,
                            },
                        },
                    },
                ],
                "name": "super",
            },
        }
