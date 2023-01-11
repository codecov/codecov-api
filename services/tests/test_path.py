from unittest.mock import patch

from django.test import TestCase
from shared.reports.types import ReportTotals
from shared.torngit.exceptions import TorngitClientGeneralError

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory
from services.archive import SerializableReport
from services.path import Dir, File, PrefixedPath, ReportPaths, provider_path_exists

# mock data

file_data1 = [
    2,
    [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]

file_data2 = [
    2,
    [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]

file_data3 = [
    2,
    [0, 10, 3, 2, 0, "30.00000", 0, 0, 0, 0, 0, 0, 0],
    [[0, 10, 3, 2, 0, "30.00000", 0, 0, 0, 0, 0, 0, 0]],
    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
]

totals1 = ReportTotals(
    files=0,
    lines=10,
    hits=8,
    misses=2,
    partials=0,
    coverage="80.00000",
    branches=0,
    methods=0,
    messages=0,
    sessions=0,
    complexity=0,
    complexity_total=0,
    diff=0,
)

totals2 = ReportTotals(
    files=0,
    lines=10,
    hits=8,
    misses=2,
    partials=0,
    coverage="80.00000",
    branches=0,
    methods=0,
    messages=0,
    sessions=0,
    complexity=0,
    complexity_total=0,
    diff=0,
)

totals3 = ReportTotals(
    files=0,
    lines=10,
    hits=3,
    misses=2,
    partials=0,
    coverage="30.00000",
    branches=0,
    methods=0,
    messages=0,
    sessions=0,
    complexity=0,
    complexity_total=0,
    diff=0,
)

# tests


class TestPathNode(TestCase):
    def setUp(self):
        self.dir = Dir(
            full_path="dir/subdir",
            children=[
                File(full_path="dir/subdir/file2.py", totals=totals1),
                File(full_path="dir/subdir/file3.py", totals=totals1),
            ],
        )

    def test_lines(self):
        # 2 files, 10 lins each
        assert self.dir.lines == 20

    def test_hits(self):
        # 2 files, 8 hits each
        assert self.dir.hits == 16

    def test_misses(self):
        # 2 files, 2 misses each
        assert self.dir.misses == 4

    def test_partials(self):
        assert self.dir.partials == 0

    def test_coverage(self):
        assert self.dir.coverage == 80.0

        file = File(full_path="file1.py", totals=ReportTotals.default_totals())
        assert file.coverage == 0

    def test_name(self):
        assert self.dir.name == "subdir"


class TestPrefixedPath(TestCase):
    def test_relative_path(self):
        path = PrefixedPath("dir/file1.py", "")
        assert path.relative_path == "dir/file1.py"

        path = PrefixedPath("dir/file1.py", "dir")
        assert path.relative_path == "file1.py"

    def test_basename(self):
        path = PrefixedPath("dir/file1.py", "")
        assert path.basename == "dir"

        path = PrefixedPath("file1.py", "")
        assert path.basename == "file1.py"

        path = PrefixedPath("dir/subdir/file1.py", "dir")
        assert path.basename == "dir/subdir"

        path = PrefixedPath("dir/subdir/file1.py", "dir/subdir")
        assert path.basename == "dir/subdir/file1.py"


class TestReportPaths(TestCase):
    def setUp(self):
        files = {
            "dir/file1.py": file_data1,
            "dir/subdir/file2.py": file_data2,
            "dir/subdir/file3.py": file_data3,
        }
        self.report = SerializableReport(files=files)

    def test_default_paths(self):
        report_paths = ReportPaths(self.report)
        assert report_paths.paths == [
            PrefixedPath("dir/file1.py", ""),
            PrefixedPath("dir/subdir/file2.py", ""),
            PrefixedPath("dir/subdir/file3.py", ""),
        ]

    def test_prefix_paths(self):
        report_paths = ReportPaths(self.report, path="dir")
        assert report_paths.paths == [
            PrefixedPath("dir/file1.py", "dir"),
            PrefixedPath("dir/subdir/file2.py", "dir"),
            PrefixedPath("dir/subdir/file3.py", "dir"),
        ]

        report_paths = ReportPaths(self.report, path="dir/subdir")
        assert report_paths.paths == [
            PrefixedPath("dir/subdir/file2.py", "dir/subdir"),
            PrefixedPath("dir/subdir/file3.py", "dir/subdir"),
        ]

    def test_search_paths(self):
        report_paths = ReportPaths(self.report, search_term="file")
        assert report_paths.paths == [
            PrefixedPath("dir/file1.py", ""),
            PrefixedPath("dir/subdir/file2.py", ""),
            PrefixedPath("dir/subdir/file3.py", ""),
        ]

        report_paths = ReportPaths(self.report, search_term="ile2")
        assert report_paths.paths == [
            PrefixedPath("dir/subdir/file2.py", ""),
        ]

    def test_full_filelist(self):
        report_paths = ReportPaths(self.report)
        assert report_paths.full_filelist() == [
            File(full_path="dir/file1.py", totals=totals1),
            File(full_path="dir/subdir/file2.py", totals=totals2),
            File(full_path="dir/subdir/file3.py", totals=totals3),
        ]

    def test_single_directory(self):
        report_paths = ReportPaths(self.report, path="dir")
        assert report_paths.single_directory() == [
            File(full_path="dir/file1.py", totals=totals1),
            Dir(
                full_path="dir/subdir",
                children=[
                    File(full_path="dir/subdir/file2.py", totals=totals2),
                    File(full_path="dir/subdir/file3.py", totals=totals3),
                ],
            ),
        ]

    def test_invalid_path(self):
        report_paths = ReportPaths(self.report, path="wrong")
        assert report_paths.paths == []


class TestReportPathsNested(TestCase):
    def setUp(self):
        files = {
            "dir/file1.py": file_data1,
            "dir/subdir/file2.py": file_data2,
            "dir/subdir/dir1/file3.py": file_data3,
            "dir/subdir/dir2/file3.py": file_data3,
            "src/ui/A/A.js": file_data3,
            "src/ui/Avatar/A.js": file_data3,
        }
        self.report = SerializableReport(files=files)

    def test_single_directory(self):
        report_paths = ReportPaths(self.report, path="dir")
        assert report_paths.single_directory() == [
            File(full_path="dir/file1.py", totals=totals1),
            Dir(
                full_path="dir/subdir",
                children=[
                    File(full_path="dir/subdir/file2.py", totals=totals2),
                    Dir(
                        full_path="dir/subdir/dir1",
                        children=[
                            File(full_path="dir/subdir/dir1/file3.py", totals=totals3),
                        ],
                    ),
                    Dir(
                        full_path="dir/subdir/dir2",
                        children=[
                            File(full_path="dir/subdir/dir2/file3.py", totals=totals3),
                        ],
                    ),
                ],
            ),
        ]

        report_paths = ReportPaths(self.report, path="src/ui/A")
        assert report_paths.single_directory() == [
            File(full_path="src/ui/A/A.js", totals=totals3),
        ]


class MockedProviderAdapter:
    async def list_files(self, *args, **kwargs):
        return []


class TestProviderPath(TestCase):
    def setUp(self):
        self.commit = CommitFactory()
        self.owner = OwnerFactory()

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_provider_path(self, mock_provider_adapter):
        mock_provider_adapter.return_value = MockedProviderAdapter()
        assert provider_path_exists("foo/bar", self.commit, self.owner) == True

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_provider_path_not_found(self, mock_provider_adapter):
        mock_provider_adapter.side_effect = TorngitClientGeneralError(404, None, None)
        assert provider_path_exists("foo/bar", self.commit, self.owner) == False

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_provider_path_other_error(self, mock_provider_adapter):
        mock_provider_adapter.side_effect = TorngitClientGeneralError(500, None, None)
        assert provider_path_exists("foo/bar", self.commit, self.owner) == None
