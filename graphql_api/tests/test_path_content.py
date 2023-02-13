from unittest.mock import Mock, PropertyMock, patch

from django.test import TransactionTestCase
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.reports.types import ReportTotals
from shared.utils.sessions import Session

from core.tests.factories import CommitFactory
from services.path import Dir, File

from ..types.commit.commit import resolve_path_contents
from ..types.errors.errors import MissingCoverage, UnknownPath
from ..types.path_contents.path_content import (
    resolve_is_critical_file,
    resolve_path_content_type,
)


def sample_report() -> Report:
    report = Report()
    first_file = ReportFile("foo/file1.py")
    first_file.append(1, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file = ReportFile("bar/file2.py")
    second_file.append(1, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session())
    return report


class MockContext(object):
    def __init__(self, context):
        self.context = context


class MockProfilingSummary:
    def __init__(self, critical_filenames):
        self.critical_filenames = critical_filenames


class TestResolvePathContent:
    def test_returns_path_content_file(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())

        type = resolve_path_content_type(file)
        assert type == "PathContentFile"

    def test_returns_path_content_dir(self):
        dir = Dir(full_path="foo/bar", children=[])

        type = resolve_path_content_type(dir)
        assert type == "PathContentDir"

    def test_returns_none(self):
        type = resolve_path_content_type("string")
        assert type == None


class TestIsCriticalFile(TransactionTestCase):
    async def test_is_critical_file_returns_true(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})
        info.context["profiling_summary"] = MockProfilingSummary(["file.py"])

        data = await resolve_is_critical_file(file, info)
        assert data == True

    async def test_is_critical_file_returns_false(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})
        info.context["profiling_summary"] = MockProfilingSummary([])

        data = await resolve_is_critical_file(file, info)
        assert data == False

    async def test_is_critical_file_no_critical_filenames(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})

        data = await resolve_is_critical_file(file, info)
        assert data == False


class TestPathContents(TransactionTestCase):
    def setUp(self):
        request = Mock()
        request.user = Mock()
        self.info = MockContext({"request": request})
        self.commit = CommitFactory()

    @patch("services.archive.ReportService.build_report_from_commit")
    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    async def test_missing_coverage(
        self, paths_mock, provider_path_exists_mock, report_mock
    ):
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = True
        report_mock.return_value = sample_report()
        res = await resolve_path_contents(self.commit, self.info, "test/path")
        assert isinstance(res, MissingCoverage)

    @patch("services.archive.ReportService.build_report_from_commit")
    @patch("services.path.provider_path_exists")
    @patch("services.path.ReportPaths.paths", new_callable=PropertyMock)
    async def test_unknown_path(
        self, paths_mock, provider_path_exists_mock, report_mock
    ):
        paths_mock.return_value = []
        provider_path_exists_mock.return_value = False
        report_mock.return_value = sample_report()
        res = await resolve_path_contents(self.commit, self.info, "test/path")
        assert isinstance(res, UnknownPath)
