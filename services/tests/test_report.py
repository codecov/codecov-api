from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    CommitWithReportFactory,
)
from shared.reports.api_report_service import (
    build_report,
    build_report_from_commit,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.storage.exceptions import FileNotInStorageError
from shared.utils.sessions import Session

from reports.tests.factories import UploadFactory, UploadFlagMembershipFactory
from services.report import (
    files_belonging_to_flags,
)

current_file = Path(__file__)


def flags_report():
    report = Report()
    session_a_id, _ = report.add_session(Session(flags=["flag-a"]))
    session_b_id, _ = report.add_session(Session(flags=["flag-b"]))
    session_c_id, _ = report.add_session(Session(flags=["flag-c"]))

    file_a = ReportFile("foo/file1.py")
    file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    report.append(file_a)

    file_b = ReportFile("bar/file2.py")
    file_b.append(12, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
    report.append(file_b)

    file_c = ReportFile("another/file3.py")
    file_c.append(12, ReportLine.create(coverage=1, sessions=[[session_c_id, 1]]))
    report.append(file_c)

    return report


def sorted_files(report: Report) -> list[ReportFile]:
    files = [report.get(file) for file in report.files]
    return sorted(files, key=lambda x: x.name)


class ReportServiceTest(TestCase):
    def test_report_generator(self):
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

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit(self, read_chunks_mock):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()
        commit = CommitWithReportFactory.create(message="aaaaa", commitid="abf6d4d")
        commit_report = commit.reports.first()

        # this will be ignored
        UploadFactory(
            report=commit_report,
            order_number=None,
            storage_path="v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
            state="error",
        )

        res = build_report_from_commit(commit)
        assert len(res._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted_files(res)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0)
        read_chunks_mock.assert_called_with("abf6d4d")
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

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_file_not_in_storage(self, read_chunks_mock):
        read_chunks_mock.side_effect = FileNotInStorageError()
        commit = CommitWithReportFactory.create(message="aaaaa", commitid="abf6d4d")
        assert build_report_from_commit(commit) is None

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_cff_and_direct_uploads(self, read_chunks_mock):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()

        commit = CommitWithReportFactory.create()
        commit_report = commit.reports.first()

        # this upload will be ignored since there's another direct
        # upload with the same flag
        upload = UploadFactory(
            report=commit_report,
            order_number=2,
            storage_path="v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
            upload_type="carriedforward",
        )
        UploadFlagMembershipFactory(
            report_session=upload,
            flag=commit.repository.flags.get(flag_name="unittests"),
        )

        res = build_report_from_commit(commit)
        assert len(res.sessions) == 2

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_null_session_totals(self, read_chunks_mock):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()
        commit = CommitWithReportFactory.create(message="aaaaa", commitid="abf6d4d")
        upload = commit.reports.first().sessions.first()
        upload.uploadleveltotals.delete()
        res = build_report_from_commit(commit)
        assert len(res._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted_files(res)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0)
        read_chunks_mock.assert_called_with("abf6d4d")
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

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_with_flags(self, read_chunks_mock):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()
        commit = CommitWithReportFactory.create(message="aaaaa", commitid="abf6d4d")
        report = build_report_from_commit(commit)
        res = report.flags["integrations"].report
        assert len(res.report._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted_files(res)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 1, 9, 0, "10.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 0, 3, 0, "0", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 2, 5, 0, "28.57143", 0, 0, 0, 0, 0, 0, 0)
        read_chunks_mock.assert_called_with("abf6d4d")
        assert list(res.totals) == [3, 20, 3, 17, 0, "15.00000", 0, 0, 0, 1, 0, 0, 0]

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_with_non_carried_forward_flags(
        self, read_chunks_mock
    ):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()
        commit = CommitWithReportFactory.create(
            message="another test",
            commitid="asdfbhasdf89",
        )

        report = commit._report
        report["sessions"]["1"].update(
            st="carriedforward",
            se={"carriedforward_from": "56e05fced214c44a37759efa2dfc25a65d8ae98d"},
        )
        commit.save()

        commit_report = commit.reports.first()
        session = commit_report.sessions.filter(order_number=1).first()
        session.upload_type = "carriedforward"
        session.upload_extras = {
            "carriedforward_from": "56e05fced214c44a37759efa2dfc25a65d8ae98d"
        }
        session.save()

        report = build_report_from_commit(commit)
        res = report.flags["integrations"].report
        assert len(res.report._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted_files(res)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 1, 9, 0, "10.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 0, 3, 0, "0", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 2, 5, 0, "28.57143", 0, 0, 0, 0, 0, 0, 0)
        read_chunks_mock.assert_called_with("asdfbhasdf89")
        assert list(res.totals) == [3, 20, 3, 17, 0, "15.00000", 0, 0, 0, 1, 0, 0, 0]
        cff_session = res.report.sessions[1]
        assert cff_session.session_type.value == "carriedforward"
        assert (
            cff_session.session_extras["carriedforward_from"]
            == "56e05fced214c44a37759efa2dfc25a65d8ae98d"
        )

    def test_build_report_from_commit_no_report(self):
        commit = CommitFactory()
        report = build_report_from_commit(commit)
        assert report is None

    @patch("shared.api_archive.archive.ArchiveService.read_chunks")
    def test_build_report_from_commit_fallback(self, read_chunks_mock):
        f = open(current_file.parent / "samples" / "chunks.txt", "r")
        read_chunks_mock.return_value = f.read()

        report = {
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
                    "a": "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                    "c": None,
                    "d": 1547084427,
                    "e": None,
                    "f": ["unittests"],
                    "j": None,
                    "n": None,
                    "p": None,
                    "t": [3, 20, 17, 3, 0, "85.00000", 0, 0, 0, 0, 0, 0, 0],
                    "": None,
                },
                "1": {
                    "N": None,
                    "a": "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                    "c": None,
                    "d": 1547084427,
                    "e": None,
                    "f": ["integrations"],
                    "j": None,
                    "n": None,
                    "p": None,
                    "t": [3, 20, 17, 3, 0, "85.00000", 0, 0, 0, 0, 0, 0, 0],
                    "": None,
                },
            },
        }

        # there are no associated `reports_*` records but we have `commits.report` populated
        commit = CommitFactory.create(
            message="aaaaa", commitid="abf6d4d", _report=report
        )
        res = build_report_from_commit(commit)

        assert len(res._chunks) == 3
        assert len(res.files) == 3
        file_1, file_2, file_3 = sorted_files(res)
        assert file_1.name == "awesome/__init__.py"
        assert tuple(file_1.totals) == (0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0)
        assert file_2.name == "tests/__init__.py"
        assert tuple(file_2.totals) == (0, 3, 2, 1, 0, "66.66667", 0, 0, 0, 0, 0, 0, 0)
        assert file_3.name == "tests/test_sample.py"
        assert tuple(file_3.totals) == (0, 7, 7, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0)
        read_chunks_mock.assert_called_with("abf6d4d")
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

    def test_files_belonging_to_flags_with_one_flag(self):
        commit_report = flags_report()
        flags = ["flag-a"]
        files = files_belonging_to_flags(commit_report=commit_report, flags=flags)
        assert len(files) == 1
        assert files == ["foo/file1.py"]

    def test_files_belonging_to_flags_with_all_flags(self):
        commit_report = flags_report()
        flags = ["flag-a", "flag-b", "flag-c"]
        files = files_belonging_to_flags(commit_report=commit_report, flags=flags)
        assert len(files) == 3
        assert files == ["foo/file1.py", "bar/file2.py", "another/file3.py"]

    def test_files_belonging_to_flags_with_known_and_unknown_flag(self):
        commit_report = flags_report()
        flags = ["flag-a", "flag-b", "random-value-123"]
        files = files_belonging_to_flags(commit_report=commit_report, flags=flags)
        assert len(files) == 2
        assert files == ["foo/file1.py", "bar/file2.py"]

    def test_files_belonging_to_flags_with_only_unknown_flag(self):
        commit_report = flags_report()
        flags = ["random-value-123"]
        files = files_belonging_to_flags(commit_report=commit_report, flags=flags)
        assert len(files) == 0
        assert files == []
