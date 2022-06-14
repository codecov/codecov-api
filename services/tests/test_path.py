import enum
from distutils.command.build import build

from django.test import TestCase

from services.archive import SerializableReport
from services.path import (
    FilteredFilePath,
    TreeDir,
    TreeFile,
    _build_path_tree,
    _build_search_tree,
    _filter_files_by_path,
    _filtered_files_by_search,
    build_tree,
    path_tree,
    search_tree,
)

# Pulled from core.tests.factories.CommitFactory files.
# Contents don't actually matter, it's just for providing a format
# compatible with what SerializableReport expects. Used in
# ComparisonTests.
file_data = [
    2,
    [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]

# I wrote this one to have different data per file
#  so the totals aren't super obivous
file_data2 = [
    2,
    [0, 10, 3, 2, 0, "30.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 3, 2, 0, "30.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]


class MockOrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"


class MockPathContentsParameter(enum.Enum):
    NAME = "name"
    COVERAGE = "coverage"


class TestPath(TestCase):
    def test_build_tree_without_filters_or_path(self):
        files = {
            "rand/path/file1.py": file_data,
            "rand/path/file2.py": file_data,
            "weird/poth/file3.py": file_data,
        }
        commit_report = SerializableReport(files=files)
        files_list = [f for f in files.keys()]
        path = ""
        filters = {}
        tree = build_tree(files_list, path, filters, commit_report)

        expected_result = [
            TreeDir(
                kind="dir",
                name="rand",
                hits=16,
                lines=20,
                coverage=80.0,
                children=[
                    TreeDir(
                        kind="dir",
                        name="path",
                        hits=16,
                        lines=20,
                        coverage=80.0,
                        children=[
                            TreeFile(
                                kind="file",
                                name="file1.py",
                                hits=8,
                                lines=10,
                                coverage=80.0,
                                full_path="rand/path/file1.py",
                            ),
                            TreeFile(
                                kind="file",
                                name="file2.py",
                                hits=8,
                                lines=10,
                                coverage=80.0,
                                full_path="rand/path/file2.py",
                            ),
                        ],
                    )
                ],
            ),
            TreeDir(
                kind="dir",
                name="weird",
                hits=8,
                lines=10,
                coverage=80.0,
                children=[
                    TreeDir(
                        kind="dir",
                        name="poth",
                        hits=8,
                        lines=10,
                        coverage=80.0,
                        children=[
                            TreeFile(
                                kind="file",
                                name="file3.py",
                                hits=8,
                                lines=10,
                                coverage=80.0,
                                full_path="weird/poth/file3.py",
                            )
                        ],
                    )
                ],
            ),
        ]
        assert tree == expected_result

    def test_build_tree_with_search_value(self):
        files = {
            "rand/path/file1.py": file_data,
            "rand/path/file2.py": file_data,
            "weird/poth/file3.py": file_data,
        }
        commit_report = SerializableReport(files=files)
        files_list = [f for f in files.keys()]
        path = ""
        filters = {"searchValue": "rand"}
        tree = build_tree(files_list, path, filters, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file1.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file1.py",
            ),
            TreeFile(
                kind="file",
                name="file2.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file2.py",
            ),
        ]
        assert tree == expected_result

    def test_build_tree_with_ascending_name(self):
        files = {"aaa.py": file_data, "zzz.py": file_data}
        commit_report = SerializableReport(files=files)
        files_list = [f for f in files.keys()]
        path = ""
        filters = {
            "orderingDirection": MockOrderingDirection.ASC,
            "orderingParameter": MockPathContentsParameter.NAME,
        }
        tree = build_tree(files_list, path, filters, commit_report)
        expected_result = [
            TreeFile(
                kind="file",
                name="aaa.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="aaa.py",
            ),
            TreeFile(
                kind="file",
                name="zzz.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="zzz.py",
            ),
        ]
        assert tree == expected_result

    def test_build_tree_with_descending_name(self):
        files = {"aaa.py": file_data, "zzz.py": file_data}
        commit_report = SerializableReport(files=files)
        files_list = [f for f in files.keys()]
        path = ""
        filters = {
            "orderingDirection": MockOrderingDirection.DESC,
            "orderingParameter": MockPathContentsParameter.NAME,
        }
        tree = build_tree(files_list, path, filters, commit_report)
        expected_result = [
            TreeFile(
                kind="file",
                name="zzz.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="zzz.py",
            ),
            TreeFile(
                kind="file",
                name="aaa.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="aaa.py",
            ),
        ]
        assert tree == expected_result

    def test_build_tree_with_descending_coverage(self):
        files = {"aaa.py": file_data, "zzz.py": file_data2}
        commit_report = SerializableReport(files=files)
        files_list = [f for f in files.keys()]
        path = ""
        filters = {
            "orderingDirection": MockOrderingDirection.DESC,
            "orderingParameter": MockPathContentsParameter.COVERAGE,
        }
        tree = build_tree(files_list, path, filters, commit_report)
        expected_result = [
            TreeFile(
                kind="file",
                name="aaa.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="aaa.py",
            ),
            TreeFile(
                kind="file",
                name="zzz.py",
                hits=3,
                lines=10,
                coverage=30.0,
                full_path="zzz.py",
            ),
        ]
        assert tree == expected_result

    def test_path_tree_with_path(self):
        files = {"folder/file.py": file_data}
        files_list = [f for f in files.keys()]
        path = "folder"
        commit_report = SerializableReport(files=files)
        tree = path_tree(files_list, path, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="folder/file.py",
            )
        ]
        assert tree == expected_result

    def test_search_tree_with_search_value(self):
        files = {
            "rand/path/file1.py": file_data,
            "rand/path/file2.py": file_data,
            "weird/poth/file3.py": file_data,
        }
        files_list = [f for f in files.keys()]
        search = "rand"
        commit_report = SerializableReport(files=files)
        tree = search_tree(files_list, search, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file1.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file1.py",
            ),
            TreeFile(
                kind="file",
                name="file2.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file2.py",
            ),
        ]
        assert tree == expected_result

    def test_build_path_tree_with_one_path(self):
        files = {"file.py": file_data}
        commit_report = SerializableReport(files=files)
        paths = [FilteredFilePath(full_path="file.py", stripped_path="file.py")]
        tree = _build_path_tree(paths, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="file.py",
            )
        ]
        assert tree == expected_result

    def test_build_path_tree_with_one_stripped_path(self):
        files = {"folder/file.py": file_data}
        commit_report = SerializableReport(files=files)
        paths = [FilteredFilePath(full_path="folder/file.py", stripped_path="file.py")]
        tree = _build_path_tree(paths, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="folder/file.py",
            )
        ]
        assert tree == expected_result

    def test_build_path_tree_with_many_paths(self):
        files = {"file1.py": file_data, "file2.py": file_data, "file3.py": file_data}
        commit_report = SerializableReport(files=files)
        paths = [
            FilteredFilePath(full_path=path, stripped_path=path)
            for path in files.keys()
        ]
        tree = _build_path_tree(paths, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file1.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="file1.py",
            ),
            TreeFile(
                kind="file",
                name="file2.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="file2.py",
            ),
            TreeFile(
                kind="file",
                name="file3.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="file3.py",
            ),
        ]
        assert tree == expected_result

    def test_build_path_tree_with_many_nested_paths(self):
        files = {
            "fileA.py": file_data,
            "folder/fileB.py": file_data2,
            "folder/subfolder/fileC.py": file_data,
            "folder/subfolder/fileD.py": file_data2,
        }
        commit_report = SerializableReport(files=files)
        paths = [
            FilteredFilePath(full_path=path, stripped_path=path)
            for path in files.keys()
        ]
        tree = _build_path_tree(paths, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="fileA.py",
                hits=8,
                lines=10,
                coverage=80.00000,
                full_path="fileA.py",
            ),
            TreeDir(
                kind="dir",
                name="folder",
                hits=14,
                lines=30,
                coverage=46.666666666666664,
                children=[
                    TreeFile(
                        kind="file",
                        name="fileB.py",
                        hits=3,
                        lines=10,
                        coverage=30.00000,
                        full_path="folder/fileB.py",
                    ),
                    TreeDir(
                        kind="dir",
                        name="subfolder",
                        hits=11,
                        lines=20,
                        coverage=55.00000000000001,
                        children=[
                            TreeFile(
                                kind="file",
                                name="fileC.py",
                                hits=8,
                                lines=10,
                                coverage=80.00000,
                                full_path="folder/subfolder/fileC.py",
                            ),
                            TreeFile(
                                kind="file",
                                name="fileD.py",
                                hits=3,
                                lines=10,
                                coverage=30.00000,
                                full_path="folder/subfolder/fileD.py",
                            ),
                        ],
                    ),
                ],
            ),
        ]
        assert tree == expected_result

    def test_build_search_tree(self):
        files = {
            "rand/path/file1.py": file_data,
            "rand/path/file2.py": file_data,
            "rand/path/file3.py": file_data,
        }
        commit_report = SerializableReport(files=files)
        paths = [path for path in files.keys()]
        tree = _build_search_tree(paths, commit_report)

        expected_result = [
            TreeFile(
                kind="file",
                name="file1.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file1.py",
            ),
            TreeFile(
                kind="file",
                name="file2.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file2.py",
            ),
            TreeFile(
                kind="file",
                name="file3.py",
                hits=8,
                lines=10,
                coverage=80.0,
                full_path="rand/path/file3.py",
            ),
        ]
        assert tree == expected_result

    def test_filter_files_by_empty_path_prefix(self):
        file_list = [
            "fileA.py",
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]
        path_prefix = ""

        filtered_file_paths = _filter_files_by_path(file_list, path_prefix)

        expected_result = [
            FilteredFilePath(full_path="fileA.py", stripped_path="fileA.py"),
            FilteredFilePath(
                full_path="folder/fileB.py", stripped_path="folder/fileB.py"
            ),
            FilteredFilePath(
                full_path="folder/subfolder/fileC.py",
                stripped_path="folder/subfolder/fileC.py",
            ),
            FilteredFilePath(
                full_path="folder/subfolder/fileD.py",
                stripped_path="folder/subfolder/fileD.py",
            ),
        ]

        assert filtered_file_paths == expected_result

    def test_filter_files_by_non_empty_path_prefix(self):
        file_list = [
            "fileA.py",
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]
        path_prefix = "folder/subfolder"

        filtered_file_paths = _filter_files_by_path(file_list, path_prefix)

        expected_result = [
            FilteredFilePath(
                full_path="folder/subfolder/fileC.py", stripped_path="fileC.py"
            ),
            FilteredFilePath(
                full_path="folder/subfolder/fileD.py", stripped_path="fileD.py"
            ),
        ]

        assert filtered_file_paths == expected_result

    def test_filter_files_by_search(self):
        file_list = [
            "fileA.py",
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]
        search_value = "old"

        filtered_file_paths = _filtered_files_by_search(file_list, search_value)

        expected_result = [
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]

        assert filtered_file_paths == expected_result
