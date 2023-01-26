from unittest.mock import PropertyMock, patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.reports.types import ReportTotals
from shared.utils.merge import LineType
from shared.utils.sessions import Session

import services.comparison as comparison
from api.shared.commit.serializers import ReportTotalsSerializer
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from services.archive import SerializableReport
from services.components import Component


def sample_report1():
    report = Report()
    first_file = ReportFile("foo/file1.py")
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
    second_file = ReportFile("bar/file2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


def sample_report2():
    report = Report()
    first_file = ReportFile("foo/file1.py")
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
    first_file.append(11, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    second_file = ReportFile("bar/file2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(13, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


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


@patch("services.comparison.Comparison.has_unmerged_base_commits", lambda self: True)
@patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
@patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
@patch("services.repo_providers.RepoProviderService.get_adapter")
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
                        "segments": [
                            {
                                "header": ["4", "43", "4", "3"],
                                "lines": ["", "", ""] + ["-this line is removed"] * 40,
                            }
                        ],
                        "stats": {"removed": 40, "added": 0},
                        "totals": ReportTotals.default_totals(),
                    }
                }
            },
        }

        self.mocked_compare_adapter = MockedComparisonAdapter(
            self.mock_git_compare_data
        )

        self.base_file = ReportFile(
            name=self.file_name, totals=[46, 46, 0, 0, 100, 0, 0, 0, 1, 0, 0, 0]
        )
        self.base_file._lines = [[1, "", [[1, 1, 0, 0, 0]], 0, 0]] * 46
        self.base_report = MockSerializableReport()
        self.base_report.mocked_files = {self.file_name: self.base_file}

        self.head_file = ReportFile(
            name=self.file_name, totals=[6, 6, 0, 0, 100, 0, 0, 0, 1, 0, 0, 0]
        )
        self.head_file._lines = [[1, "", [[1, 1, 0, 0, 0]], 0, 0]] * 6
        self.head_file.totals.diff = ReportTotals.default_totals()
        self.head_report = MockSerializableReport()
        self.head_report.mocked_files = {self.file_name: self.head_file}

        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.base, self.head = (
            CommitFactory(repository=self.repo),
            CommitFactory(repository=self.repo),
        )
        self.user = OwnerFactory(
            service=self.org.service,
            permission=[self.repo.repoid],
            organizations=[self.org.ownerid],
        )
        self.client.force_login(user=self.user)

        self.expected_files = [
            {
                "name": {"base": self.file_name, "head": self.file_name},
                "totals": {
                    "base": ReportTotalsSerializer(self.base_file.totals).data,
                    "head": ReportTotalsSerializer(self.head_file.totals).data,
                    "patch": ReportTotalsSerializer(ReportTotals.default_totals()).data,
                },
                "has_diff": True,
                "stats": {"added": 0, "removed": 40},
                "change_summary": {},
                "lines": [
                    {
                        "value": "",
                        "number": {"base": idx, "head": idx},
                        "coverage": {"base": LineType.hit, "head": LineType.hit},
                        "added": False,
                        "removed": False,
                        "is_diff": True,
                        "sessions": 1,
                    }
                    for idx in range(4, 7)
                ]
                + [
                    {
                        "value": "-this line is removed",
                        "number": {"base": idx, "head": None},
                        "coverage": {"base": LineType.hit, "head": None},
                        "added": False,
                        "removed": True,
                        "is_diff": True,
                        "sessions": None,
                    }
                    for idx in range(7, 47)
                ],
            }
        ]

    def _get_comparison(self, kwargs={}, query_params={}):
        if kwargs == {}:
            kwargs = {
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            }
        if query_params == {}:
            query_params = {"base": self.base.commitid, "head": self.head.commitid}

        return self.client.get(
            reverse("api-v2-compare-detail", kwargs=kwargs),
            data=query_params,
            content_type="application/json",
        )

    def _get_file_comparison(self, file_name="", kwargs={}, query_params={}):
        if kwargs == {}:
            kwargs = {
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
                "file_path": file_name or self.file_name,
            }
        if query_params == {}:
            query_params = {"base": self.base.commitid, "head": self.head.commitid}

        return self.client.get(
            reverse("api-v2-compare-file", kwargs=kwargs),
            data=query_params,
            content_type="application/json",
        )

    def _get_flag_comparison(self, kwargs=None, query_params=None):
        if kwargs is None:
            kwargs = {
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            }
        if query_params is None:
            query_params = {"base": self.base.commitid, "head": self.head.commitid}

        return self.client.get(
            reverse("api-v2-compare-flags", kwargs=kwargs),
            data=query_params,
            content_type="application/json",
        )

    def test_can_return_public_repo_comparison_with_not_authenticated(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        public_repo = RepositoryFactory(author=self.org, private=False)
        base, head = (
            CommitFactory(repository=public_repo),
            CommitFactory(repository=public_repo),
        )

        self.client.logout()
        response = self._get_comparison(
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": public_repo.name,
            },
            query_params={"base": base.commitid, "head": head.commitid},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_returns_200_and_expected_files_on_success(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"] == self.expected_files
        assert response.data["has_unmerged_base_commits"] is True

    def test_returns_404_if_base_or_head_references_not_found(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        response = self._get_comparison(query_params={"base": 12345, "head": 678})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_404_if_user_doesnt_have_permissions(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        other_user = OwnerFactory()
        self.client.force_login(user=other_user)

        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == 404

    @patch("redis.Redis.get", lambda self, key: None)
    @patch("redis.Redis.set", lambda self, key, val, ex: None)
    def test_accepts_pullid_query_param(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head=self.head.commitid,
                    compared_to=self.base.commitid,
                    pullid=2,
                    repository=self.repo,
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"] == self.expected_files

    def test_pullid_with_nonexistent_base_returns_404(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base="123456",
                    head=self.head.commitid,
                    pullid=2,
                    repository=self.repo,
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pullid_with_nonexistent_head_returns_404(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head="123456",
                    compared_to=self.base.commitid,
                    pullid=2,
                    repository=self.repo,
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_diffs_larger_than_MAX_DIFF_SIZE_doesnt_include_lines(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        previous_max = comparison.MAX_DIFF_SIZE
        comparison.MAX_DIFF_SIZE = (
            len(
                self.mock_git_compare_data["diff"]["files"][self.file_name]["segments"][
                    0
                ]["lines"]
            )
            - 1
        )

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert (
            response.data["files"][0]["lines"] == None
        )  # None means diff was truncated

        comparison.MAX_DIFF_SIZE = previous_max

    def test_file_returns_comparefile_with_diff_and_src_data(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        src = b"first\nfirst\nfirst\nfirst\nfirst\nfirst"

        adapter_mock.return_value = MockedComparisonAdapter(
            test_diff=self.mock_git_compare_data, test_lines=src
        )

        response = self._get_file_comparison()

        assert response.status_code == status.HTTP_200_OK

        expected_lines = [
            {
                "value": "first",
                "number": {"base": idx, "head": idx},
                "coverage": {"base": LineType.hit, "head": LineType.hit},
                "added": False,
                "removed": False,
                "is_diff": False,
                "sessions": 1,
            }
            for idx in range(1, 4)
        ] + self.expected_files[0]["lines"]

        assert response.data["lines"] == expected_lines

    def test_file_ignores_MAX_DIFF_SIZE(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        previous_max = comparison.MAX_DIFF_SIZE
        comparison.MAX_DIFF_SIZE = -1

        src = b"first\nfirst\nfirst\nfirst\nfirst\nfirst"
        adapter_mock.return_value = MockedComparisonAdapter(
            test_diff=self.mock_git_compare_data, test_lines=src
        )

        response = self._get_file_comparison()

        comparison.MAX_DIFF_SIZE = previous_max

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["lines"]) == 46

    def test_missing_base_report_returns_none_base_totals(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.return_value = self.head_report
        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["totals"]["base"] == None

    def test_no_raw_reports_returns_404(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        base_report_mock.return_value = None
        head_report_mock.side_effect = comparison.MissingComparisonReport(
            "Missing head report"
        )
        adapter_mock.return_value = self.mocked_compare_adapter

        response = self._get_comparison()

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_returns_403_if_user_inactive(
        self, adapter_mock, base_report_mock, head_report_mock
    ):
        self.org.plan = "users-inappy"
        self.org.plan_auto_activate = False
        self.org.save()

        response = self._get_comparison()
        assert response.status_code == 403

    @patch("redis.Redis.get", lambda self, key: None)
    @patch("redis.Redis.set", lambda self, key, val, ex: None)
    @patch(
        "services.comparison.PullRequestComparison.pseudo_diff_adjusts_tracked_lines",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.PullRequestComparison.allow_coverage_offsets",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.PullRequestComparison.update_base_report_with_pseudo_diff"
    )
    def test_pull_request_pseudo_comparison_can_update_base_report(
        self,
        update_base_report_mock,
        allow_coverage_offsets_mock,
        pseudo_diff_adjusts_tracked_lines_mock,
        adapter_mock,
        base_report_mock,
        head_report_mock,
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        allow_coverage_offsets_mock.return_value = True

        pseudo_diff_adjusts_tracked_lines_mock.return_value = True

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head=self.head.commitid,
                    compared_to=self.base.commitid,
                    pullid=2,
                    repository=self.repo,
                ).pullid
            }
        )

        update_base_report_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["files"] == self.expected_files

    @patch("redis.Redis.get", lambda self, key: None)
    @patch("redis.Redis.set", lambda self, key, val, ex: None)
    @patch(
        "services.comparison.PullRequestComparison.pseudo_diff_adjusts_tracked_lines",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.PullRequestComparison.allow_coverage_offsets",
        new_callable=PropertyMock,
    )
    @patch(
        "services.comparison.PullRequestComparison.update_base_report_with_pseudo_diff"
    )
    def test_pull_request_pseudo_comparison_returns_error_if_coverage_offsets_not_allowed(
        self,
        update_base_report_mock,
        allow_coverage_offsets_mock,
        pseudo_diff_adjusts_tracked_lines_mock,
        adapter_mock,
        base_report_mock,
        head_report_mock,
    ):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        pseudo_diff_adjusts_tracked_lines_mock.return_value = True
        allow_coverage_offsets_mock.return_value = False

        response = self._get_comparison(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head=self.head.commitid,
                    compared_to=self.base.commitid,
                    pullid=2,
                    repository=self.repo,
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_flags_comparison(self, adapter_mock, base_report_mock, head_report_mock):
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = self.base_report
        head_report_mock.return_value = self.head_report

        res = self._get_flag_comparison()
        assert res.status_code == 200

    @patch("api.public.v2.compare.views.commit_components")
    def test_components_comparison(
        self, commit_components, adapter_mock, base_report_mock, head_report_mock
    ):
        commit_components.return_value = [
            Component(
                component_id="foo",
                paths=[r"^foo/.+"],
                name="Foo",
                flag_regexes=[],
                statuses=[],
            ),
            Component(
                component_id="bar",
                paths=[r"^bar/.+"],
                name="Bar",
                flag_regexes=[],
                statuses=[],
            ),
        ]
        adapter_mock.return_value = self.mocked_compare_adapter
        base_report_mock.return_value = sample_report1()
        head_report_mock.return_value = sample_report2()

        res = self.client.get(
            reverse(
                "api-v2-compare-components",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            ),
            data={
                "base": self.base.commitid,
                "head": self.head.commitid,
            },
            content_type="application/json",
        )

        assert res.status_code == 200
        assert res.json() == [
            {
                "component_id": "foo",
                "name": "Foo",
                "base_report_totals": {
                    "files": 1,
                    "lines": 8,
                    "hits": 5,
                    "misses": 3,
                    "partials": 0,
                    "coverage": 62.5,
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 1,
                    "complexity": 10.0,
                    "complexity_total": 2.0,
                    "complexity_ratio": 500.0,
                    "diff": 0,
                },
                "head_report_totals": {
                    "files": 1,
                    "lines": 9,
                    "hits": 5,
                    "misses": 4,
                    "partials": 0,
                    "coverage": 55.56,
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 1,
                    "complexity": 10.0,
                    "complexity_total": 2.0,
                    "complexity_ratio": 500.0,
                    "diff": 0,
                },
                "diff_totals": {
                    "files": 0,
                    "lines": 0,
                    "hits": 0,
                    "misses": 0,
                    "partials": 0,
                    "coverage": 0,
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 0,
                    "complexity": None,
                    "complexity_total": None,
                    "complexity_ratio": 0,
                    "diff": 0,
                },
            },
            {
                "component_id": "bar",
                "name": "Bar",
                "base_report_totals": {
                    "files": 1,
                    "lines": 2,
                    "hits": 1,
                    "misses": 0,
                    "partials": 1,
                    "coverage": 50.0,
                    "branches": 1,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 1,
                    "complexity": 0.0,
                    "complexity_total": 0.0,
                    "complexity_ratio": 0,
                    "diff": 0,
                },
                "head_report_totals": {
                    "files": 1,
                    "lines": 3,
                    "hits": 2,
                    "misses": 0,
                    "partials": 1,
                    "coverage": 66.67,
                    "branches": 1,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 1,
                    "complexity": 0.0,
                    "complexity_total": 0.0,
                    "complexity_ratio": 0,
                    "diff": 0,
                },
                "diff_totals": {
                    "files": 0,
                    "lines": 0,
                    "hits": 0,
                    "misses": 0,
                    "partials": 0,
                    "coverage": 0,
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 0,
                    "complexity": None,
                    "complexity_total": None,
                    "complexity_ratio": 0,
                    "diff": 0,
                },
            },
        ]
