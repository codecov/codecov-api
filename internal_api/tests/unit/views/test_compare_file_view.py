import json

from django.test import override_settings

from core.tests.factories import RepositoryFactory, CommitFactory


class TestCompareSingleFileChangesView(object):

    @override_settings(DEBUG=True)
    def test_fetch_file_cov_decrease___success(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/src_file/src/subtractor/subtractor.py'
        print("request url: ", url)
        response = client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['src'] == {
            "base": None,
            "head": [
                "import math",
                "",
                "class Subtractor(object):",
                "    def subtract(self, x, y):",
                "        return x - y",
                "    ",
                "    def divide(self, x, y):",
                "        return float(x) / float(y)",
                "    ",
                "    def fractionate(self, x):",
                "        return 1 / float(x)",
                "    ",
                "    def half(self, x):",
                "        return float(x) / 2"
            ]
        }

    @override_settings(DEBUG=True)
    def test_fetch_file_with_filename_change(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/src_file/src/adder/adders.py?before=src/adder/adder.py'
        print("request url: ", url)
        response = client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content == {
            "src": {
                "base": [
                    "import math",
                    "",
                    "class Adder(object):",
                    "    def add(self, x, y):",
                    "        # a line --",
                    "        # another line",
                    "        # a third line",
                    "        return x + y",
                    "        ",
                    "    def multiply(self, x, y):",
                    "        return x * y"
                ],
                "head": [
                    "import math",
                    "",
                    "class Adder(object):",
                    "    def add(self, x, y):",
                    "        # a line --",
                    "        # another line",
                    "        # a third line",
                    "        return x + y",
                    "        ",
                    "    def multiply(self, x, y):",
                    "        return x * y",
                    "    ",
                    "    def add2(self, x):",
                    "        return x + 2"
                ]
            }
        }

    @override_settings(DEBUG=True)
    def test_fetch_file_with_diff_change(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head, change_commit = build_commits_with_changes(client=client)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{change_commit.commitid}/src_file/tests/unit/adder/test_adder.py'
        print("request url: ", url)
        response = client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content == {
            "src": {
                "base": None,
                "head": [
                    "import pytest",
                    "from src.adder.adders import Adder",
                    "",
                    "def test_sum_two_plus_two_is_four():",
                    "    assert Adder().add(3,3) == 6",
                    "",
                    "def test_sum_two_plus_two_is_not_five():",
                    "    assert Adder().add(3,4) != 6",
                    "",
                    "def test_add2_with_four():",
                    "\tassert Adder().add2(4) == 6"
                ]
            }
        }


def build_commits_with_changes(client):
    """
        build commits in mock_db that are based on a real git comparison with a change in file coverage for using VCR
    :param client:
    :return: repo, commit_base, commit_head
    """
    repo = RepositoryFactory.create(
        author__unencrypted_oauth_token='2ee59e1b1fea82341f3d12d2df82dffb19dfe965',
        author__username='eyoel-cov',
        name='codecov-assume-flag-test',
        service_id='191251616',
        repoid=113

    )
    parent_commit = CommitFactory.create(
        message='test_compare_parent',
        commitid='7bc5fa7',
        repository=repo,
    )
    commit_base_report = {"files": {"src/adder/adder.py": [3, [0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0]], None], "src/subtractor/subtractor.py": [2, [0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/adder/test_adder.py": [1, [0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/subtractor/test_subtractor.py": [0, [0, 12, 12, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 12, 12, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None]}, "sessions": {"0": {"N": None, "a": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/7e23d61d-0aa2-4dc2-9ff3-1f30ec1260d8.txt", "c": None, "d": 1566969609, "e": None, "f": None, "j": None, "n": None, "p": None, "t": [4, 34, 33, 1, 0, "97.05882", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/7e23d61d-0aa2-4dc2-9ff3-1f30ec1260d8.txt"}}}
    commit_base = CommitFactory.create(
        message='test_compare_commits_base',
        commitid='791886122b02a2e52e5dd09e8be5f92e09e83f0b',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
        report=commit_base_report
    )
    commit_head_report = {"files": {"src/adder/adders.py": [4, [0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0]], [0, 0, 0, 0, 0, None, 0, 0, 0, 0, None, None, 0]], "tests/unit/test_main.py": [1, [0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], "src/subtractor/subtractor.py": [3, [0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/adder/test_adder.py": [0, [0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 1, 1, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], "tests/unit/subtractor/test_subtractor.py": [2, [0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 0, 0, 0, 0, None, 0, 0, 0, 0, None, None, 0]]}, "sessions": {"0": {"N": None, "a": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/e8c50db9-8ba4-47d6-99cf-d6d700ad0947.txt", "c": None, "d": 1566971059, "e": None, "f": None, "j": None, "n": None, "p": None, "t": [5, 36, 34, 2, 0, "94.44444", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/e8c50db9-8ba4-47d6-99cf-d6d700ad0947.txt"}}}
    commit_head = CommitFactory.create(
        message='test_compare_commits_head',
        commitid='f64b22e6af4bbe3917ac4a7c346feb03493c2b67',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
        report=commit_head_report

    )
    commit_with_change_report = {"files": {"src/adder/adders.py": [4, [0, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0], [[0, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/test_main.py": [1, [0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 1, 1, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], "src/subtractor/subtractor.py": [3, [0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/adder/test_adder.py": [0, [0, 8, 8, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 8, 8, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/subtractor/test_subtractor.py": [2, [0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None]}, "sessions": {"0": {"N": None, "a": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/48a4883890d71d777794ed998a1ad4d24a9ebab5/3ca46d25-5ee5-4e66-beba-6056acaf5dea.txt", "c": None, "d": 1566958278, "e": None, "f": None, "j": None, "n": None, "p": None, "t": [5, 40, 38, 2, 0, "95.00000", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/48a4883890d71d777794ed998a1ad4d24a9ebab5/3ca46d25-5ee5-4e66-beba-6056acaf5dea.txt"}}}
    file_change_commit = CommitFactory.create(
        message='test_compare_commits_with_filechange',
        commitid='48a4883890d71d777794ed998a1ad4d24a9ebab5',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
        report=commit_head_report

    )
    client.force_login(user=repo.author)
    return repo, commit_base, commit_head, file_change_commit
