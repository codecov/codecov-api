from graphql import GraphQLResolveInfo
from shared.reports.types import ReportTotals

from services.path import Dir, File

from ..types.path_contents.path_content import (
    resolve_is_critical_file,
    resolve_path_content_type,
)


class MockContext(object):
    def __init__(self, context):
        self.context = context


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


class TestIsCriticalFile:
    def test_is_critical_file_returns_true(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})
        info.context["critical_filenames"] = ["file.py"]

        data = resolve_is_critical_file(file, info)
        assert data == True

    def test_is_critical_file_returns_false(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})
        info.context["critical_filenames"] = []

        data = resolve_is_critical_file(file, info)
        assert data == False

    def test_is_critical_file_no_critical_filenames(self):
        file = File(full_path="file.py", totals=ReportTotals.default_totals())
        info = MockContext(context={})

        data = resolve_is_critical_file(file, info)
        assert data == False
