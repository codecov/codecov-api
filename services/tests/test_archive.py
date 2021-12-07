from pathlib import Path

from core.models import Repository
from core.tests.factories import CommitFactory, RepositoryFactory
from services.archive import ArchiveService, MinioEndpoints, ReportService, build_report
from services.storage import StorageService

current_file = Path(__file__)


class TestReport(object):
    def test_report_generator(self, codecov_vcr):
        data = {
            "chunks": "{}\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[0, null, [[0, 0]]]\n<<<<< end_of_chunk >>>>>\n{}\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n<<<<< end_of_chunk >>>>>\n{}\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[0, null, [[0, 0]]]\n\n\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n[1, null, [[0, 1]]]\n\n\n[1, null, [[0, 1]]]\n[0, null, [[0, 0]]]",
            "files": {
                "awesome/__init__.py": [
                    2,
                    [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
                    [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
                    [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                ],
                "tests/__init__.py": [
                    0,
                    [0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0],
                    [[0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0]],
                    None,
                ],
                "tests/test_sample.py": [
                    1,
                    [0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0],
                    [[0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]],
                    None,
                ],
            },
            "sessions": {
                "0": {
                    "N": None,
                    "a": "v4/raw/2019-01-10/839C9EAF1A3F1CD45AA08DF5F791461F/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                    "c": None,
                    "d": 1547084427,
                    "e": None,
                    "f": None,
                    "j": None,
                    "n": None,
                    "p": None,
                    "t": [3, 20, 17, 3, 0, "85.00000", 0, 0, 0, 0, 0, 0, 0],
                    "": None,
                }
            },
            "totals": {
                "C": 0,
                "M": 0,
                "N": 0,
                "b": 0,
                "c": "85.00000",
                "d": 0,
                "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
                "f": 3,
                "h": 17,
                "m": 3,
                "n": 20,
                "p": 0,
                "s": 1,
            },
        }

        res = build_report(**data)
        assert len(res._chunks) == 3

    def test_build_report_from_commit(self, db, mocker, codecov_vcr):
        mocked = mocker.patch.object(ArchiveService, "read_chunks")
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        mocked.return_value = f.read()
        commit = CommitFactory.create(message="aaaaa", commitid="abf6d4d")
        res = ReportService().build_report_from_commit(commit)
        assert len(res._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted(res.file_reports(), key=lambda x: x.name)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0)
        mocked.assert_called_with("abf6d4d")
        assert list(res.totals) == [
            3,
            20,
            17,
            3,
            0,
            "85.00000",
            0,
            0,
            0,
            1,
            0,
            0,
            [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
        ]

    def test_build_report_from_commit_with_flags(self, db, mocker, codecov_vcr):
        mocked = mocker.patch.object(ArchiveService, "read_chunks")
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        mocked.return_value = f.read()
        commit = CommitFactory.create(message="aaaaa", commitid="abf6d4d")
        report = ReportService().build_report_from_commit(commit)
        res = report.flags["integrations"].report
        assert len(res.report._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted(res.file_reports(), key=lambda x: x.name)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 1, 9, 0, "10.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 0, 3, 0, "0", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 2, 5, 0, "28.57143", 0, 0, 0, 0, 0, 0, 0)
        mocked.assert_called_with("abf6d4d")
        assert list(res.totals) == [3, 20, 3, 17, 0, "15.00000", 0, 0, 0, 1, 0, 0, 0]

    def test_build_report_from_commit_no_report(self, db, mocker, codecov_vcr):
        commit = CommitFactory(report=None)
        report = ReportService().build_report_from_commit(commit)
        assert report is None

    def test_create_raw_upload_presigned_put(self, db, mocker, codecov_vcr):
        mocked = mocker.patch.object(StorageService, "create_presigned_put")
        mocked.return_value = "presigned url"
        repo = RepositoryFactory.create()
        service = ArchiveService(repo)
        assert service.create_raw_upload_presigned_put("ABCD") == "presigned url"
