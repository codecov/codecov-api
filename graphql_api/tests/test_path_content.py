from graphql import GraphQLResolveInfo

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
        file = File(
            kind="kind",
            name="name",
            hits=1,
            lines=1,
            coverage=1.1,
            full_path="full path",
        )

        type = resolve_path_content_type(file)

        assert type == "PathContentFile"

    def test_returns_path_content_dir(self):
        dir = Dir(kind="kind", name="name", hits=1, lines=1, coverage=1.1, children=[])

        type = resolve_path_content_type(dir)

        assert type == "PathContentDir"

    def test_returns_none(self):
        type = resolve_path_content_type("string")

        assert type == None


class TestIsCriticalFile:
    def test_is_critical_file_returns_true(self):
        file = File(
            kind="kind", name="name", hits=1, lines=1, coverage=1.1, full_path="file.py"
        )

        info = MockContext(context={})
        info.context["critical_filenames"] = ["file.py"]

        data = resolve_is_critical_file(file, info)

        assert data == True

    def test_is_critical_file_returns_false(self):
        file = File(
            kind="kind", name="name", hits=1, lines=1, coverage=1.1, full_path="file.py"
        )

        info = MockContext(context={})
        info.context["critical_filenames"] = []

        data = resolve_is_critical_file(file, info)

        assert data == False

    def test_is_critical_file_no_critical_filenames(self):
        file = File(
            kind="kind", name="name", hits=1, lines=1, coverage=1.1, full_path="file.py"
        )

        info = MockContext(context={})

        data = resolve_is_critical_file(file, info)

        assert data == False
