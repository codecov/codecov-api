from asgiref.sync import async_to_sync
import asyncio
import pytest
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
from shared.torngit.exceptions import TorngitObjectNotFoundError
from services.archive import SerializableReport, build_report
from ..get_file_coverage import GetFileCoverageInteractor


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


class GetFileCoverageInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetFileCoverageInteractor(current_user, service).execute(*args)

    @patch(
        "core.commands.commit.interactors.get_file_coverage.ReportService.build_report_from_commit"
    )
    @async_to_sync
    async def test_when_path_has_coverage(self, build_report_from_commit_mock):
        res = build_report(**data)
        expected_result = [
            {"line": 1, "coverage": 1},
            {"line": 2, "coverage": 1},
            {"line": 5, "coverage": 1},
            {"line": 6, "coverage": 0},
            {"line": 9, "coverage": 1},
            {"line": 10, "coverage": 1},
            {"line": 11, "coverage": 1},
            {"line": 12, "coverage": 1},
            {"line": 15, "coverage": 1},
            {"line": 16, "coverage": 0},
        ]
        build_report_from_commit_mock.return_value = res
        file_content = await self.execute(None, self.commit, "awesome/__init__.py")
        assert file_content == expected_result
