from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status
import minio

from unittest.mock import patch, PropertyMock

from shared.reports.resources import ReportFile
from shared.reports.types import ReportLine, ReportTotals, LineSession
from services.archive import SerializableReport

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory, PullFactory
from internal_api.commit.serializers import ReportTotalsSerializer

import services.comparison as comparison


class MockSerializableReport(SerializableReport):
    """
    Stubs the 'file_reports' and 'get' methods of SerializableReport, which usually constructs
    report files on the fly from information not provided by these test, like the chunks
    for example.
    """
    def file_reports(self):
        return [report_file for name, report_file in self.mocked_files.items()]

    def get(self, file_name):
        return self.mocked_files.get(file_name)

    @property
    def files(self):
        return self.mocked_files.keys()

    def __contains__(self, f):
        return f in self.mocked_files.keys()


class MockedComparisonAdapter:
    def __init__(self, test_diff, test_lines=[]):
        self.test_lines = test_lines
        self.test_diff = test_diff

    async def get_source(self, file_name, commitid):
        return {"content": self.test_lines}

    async def get_compare(self, base, head):
        return self.test_diff

    async def get_authenticated(self):
        return False, False


@patch('services.comparison.Comparison.head_report', new_callable=PropertyMock)
@patch('services.comparison.Comparison.base_report', new_callable=PropertyMock)
@patch('services.repo_providers.RepoProviderService.get_adapter')
class TestCompareViewSetRetrieve(APITestCase):
    """
    Tests for retrieving a comparison. Does not test data that will be depracated,
    eg base and head report fields. Tests for commits etc will be added as the
    compare-api refactor progresses.
    """

    def setUp(self):
        self.file_name = "myfile.py"

        self.mock_git_compare_data = {
            "commits": [],
            "diff": {
                "files": {
                    self.file_name: {
                        "type": "modified",
                        "segments": [{
                              "header": ["4", "43", "4", "3"],
                              "lines": ["", "", ""] + ["-this line is removed"]*40
                        }],
                        "stats": {
                            "removed": 40,
                            "added": 0
                        }
                    }
                }
            }
        }

        self.mocked_compare_adapter = MockedComparisonAdapter(self.mock_git_compare_data)

        self.base_file = ReportFile(name=self.file_name)
        self.base_file._lines = [ReportLine(coverage=1, sessions=[LineSession(id=1, coverage=1)])] * 46
        self.base_report = MockSerializableReport()
        self.base_report.mocked_files = {self.file_name: self.base_file}

        self.head_file = ReportFile(name=self.file_name)
        self.head_file._lines = [ReportLine(coverage=1, sessions=[LineSession(id=1, coverage=1)])] * 6
        self.head_report = MockSerializableReport()
        self.head_report.mocked_files = {self.file_name: self.head_file}

        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.base, self.head = CommitFactory(repository=self.repo), CommitFactory(repository=self.repo)
        self.user = OwnerFactory(service=self.org.service, permission=[self.repo.repoid])
        self.client.force_login(user=self.user)

        self.expected_files = [
            {
                "name": {
                    "base": self.file_name,
                    "head": self.file_name
                },
                "totals": {
                    "base": ReportTotalsSerializer(self.base_file.totals).data,
                    "head": ReportTotalsSerializer(self.head_file.totals).data
                },
                "has_diff": True,
                "stats": {
                    "added": 0,
                    "removed": 40
                },
                "change_summary": {},
                "lines": [
                    {
                        "value": "",
                        "number": {
                            "base": idx,
                            "head": idx
                        },
                        "coverage": {
                            "base": 1,
                            "head": 1
                        },
                        "added": False,
                        "removed": False,
                        "is_diff": True,
                        "sessions": 1
                    } for idx in range(4, 7)
                ] + [
                    {
                        "value": "-this line is removed",
                        "number": {
                            "base": idx,
                            "head": None
                        },
                        "coverage": {
                            "base": 1,
                            "head": None
                        },
                        "added": False,
                        "removed": True,
                        "is_diff": True,
                        "sessions": None
                    } for idx in range(7, 47)
                ]
            }
        ]

    def _get_comparison(self, kwargs={}, query_params={}):
        if kwargs == {}:
            kwargs = {
                "service": self.org.service,
                "orgName": self.org.username,
                "repoName": self.repo.name
            }
        if query_params == {}:
            query_params = {
                "base": self.base.commitid,
                "head": self.head.commitid
            }

        return self.client.get(
            reverse('compare-retrieve', kwargs=kwargs),
            data=query_params,
            content_type="application/json"
        )

    def _get_file_comparison(self, file_name='', kwargs={}, query_params={}):
        if kwargs == {}:
            kwargs = {
                "service": self.org.service,
                "orgName": self.org.username,
                "repoName": self.repo.name,
                "file_path": file_name or self.file_name
            }
        if query_params == {}:
            query_params = {
                "base": self.base.commitid,
                "head": self.head.commitid
            }

        return self.client.get(
            reverse('compare-file', kwargs=kwargs),
            data=query_params,
            content_type="application/json"
        )

    def test_returns_200_and_expected_files_on_success(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"] == self.expected_files

    def test_returns_404_if_base_or_head_references_not_found(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        response = self._get_comparison(
            query_params={"base": 12345, "head": 678}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_403_if_user_doesnt_have_permissions(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        other_user = OwnerFactory()
        self.client.force_login(user=other_user)

        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == 403

    def test_accepts_pullid_query_param(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head=self.head.commitid,
                    pullid=2,
                    repository=self.repo
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"] == self.expected_files

    def test_diffs_larger_than_MAX_DIFF_SIZE_doesnt_include_lines(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        previous_max = comparison.MAX_DIFF_SIZE
        comparison.MAX_DIFF_SIZE = len(
            self.mock_git_compare_data["diff"]["files"][self.file_name]["segments"][0]["lines"]
        ) - 1

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"][0]["lines"] == None # None means diff was truncated

        comparison.MAX_DIFF_SIZE = previous_max

    def test_file_returns_comparefile_with_diff_and_src_data(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        src = b"first\nfirst\nfirst\nfirst\nfirst\nfirst"

        adapter_mock.return_value = MockedComparisonAdapter(test_diff=self.mock_git_compare_data, test_lines=src)

        response = self._get_file_comparison()

        assert response.status_code == status.HTTP_200_OK

        expected_lines = [
            {
                "value": "first",
                "number": {
                    "base": idx,
                    "head": idx
                },
                "coverage": {
                    "base": 1,
                    "head": 1
                },
                "added": False,
                "removed": False,
                "is_diff": False,
                "sessions": 1
            } for idx in range(1, 4)
        ] + self.expected_files[0]["lines"]

        assert response.data["lines"] == expected_lines

    def test_file_ignores_MAX_DIFF_SIZE(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        previous_max = comparison.MAX_DIFF_SIZE
        comparison.MAX_DIFF_SIZE = -1

        src = b"first\nfirst\nfirst\nfirst\nfirst\nfirst"
        adapter_mock.return_value = MockedComparisonAdapter(test_diff=self.mock_git_compare_data, test_lines=src)

        response = self._get_file_comparison()

        comparison.MAX_DIFF_SIZE = previous_max

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["lines"]) == 46

    def test_missing_base_report_returns_none_base_totals(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.return_value = self.head_report
        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["totals"]["base"] == None

    def test_no_raw_reports_returns_404(
        self,
        adapter_mock,
        base_report_mock,
        head_report_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.side_effect = minio.error.NoSuchKey(response_error=None)
        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == status.HTTP_404_NOT_FOUND
