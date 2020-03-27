import json
import asyncio
from unittest.mock import patch

from core.tests.factories import RepositoryFactory, CommitFactory, PullFactory

from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from rest_framework import status


test_file_name = "test.py"
test_line = "split\nthis\nline"


class MockedGetSourceAdapter:
    async def get_source(self, file_path, commitid):
        return {"content": test_line}


@patch('services.repo_providers.RepoProviderService.get_adapter', lambda self, owner, repo: MockedGetSourceAdapter())
class TestCompareSrcFileView(APITestCase):

    def _get_src_file(self, kwargs={}, query_params={}):
        if not kwargs:
            kwargs = {
                "orgName": self.repo.author.username,
                "repoName": self.repo.name,
                "file_path": self.file_name
            }
        if not query_params:
            query_params = {
                "base": self.base.commitid,
                "head": self.head.commitid
            }
        return self.client.get(reverse('compare-src-file', kwargs=kwargs), data=query_params)

    def setUp(self):
        self.repo = RepositoryFactory()
        self.base = CommitFactory(repository=self.repo)
        self.head = CommitFactory(repository=self.repo)
        self.file_name = test_file_name

        self.client.force_login(user=self.repo.author)

    @patch('services.comparison.Comparison._calculate_base_report', lambda commit: {test_file_name: None})
    @patch('services.comparison.Comparison._calculate_head_report', lambda commit: {test_file_name: True})
    def test_no_base_file_returns_404(self):
        response = self._get_src_file()
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('services.comparison.Comparison._calculate_head_report', lambda commit: {test_file_name: None})
    @patch('services.comparison.Comparison._calculate_base_report', lambda commit: {test_file_name: True})
    def test_no_head_file_returns_404(self):
        response = self._get_src_file()
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('services.comparison.Comparison._calculate_base_report', lambda commit: {test_file_name: True})
    @patch('services.comparison.Comparison._calculate_head_report', lambda commit: {test_file_name: True})
    def test_returns_list_of_lines_on_success(self):
        response = self._get_src_file()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["src"] == test_line.splitlines()

    @patch('services.comparison.Comparison._calculate_base_report', lambda commit: {test_file_name: True})
    @patch('services.comparison.Comparison._calculate_head_report', lambda commit: {test_file_name: True})
    def test_accepts_pullid_query_param(self):
        response = self._get_src_file(
            query_params={
                "pullid": PullFactory(
                    base=self.base.commitid,
                    head=self.head.commitid,
                    repository=self.repo,
                    pullid=1,
                ).pullid
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["src"] == test_line.splitlines()


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
    commit_base_report = {"files": {"src/adder/adder.py": [3, [0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0], [0, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0]], None], "src/subtractor/subtractor.py": [2, [0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/adder/test_adder.py": [1, [0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/subtractor/test_subtractor.py": [0, [0, 12, 12, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 12, 12, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], None]}, "sessions": {"0": {"N": None, "a": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/7e23d61d-0aa2-4dc2-9ff3-1f30ec1260d8.txt", "c": None, "d": 1566969609, "e": None, "f": None, "j": None, "n": None, "p": None, "t": [4, 34, 33, 1, 0, "97.05882", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/7e23d61d-0aa2-4dc2-9ff3-1f30ec1260d8.txt"}, "1": {"N": None, "a": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/3879b633-613e-4c25-8939-35f147e9d113.txt", "c": None, "d": 1567640899, "e": None, "f": ["adder", "assumeflag"], "j": None, "n": None, "p": None, "t": None, "u": None, "storage_path": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/3879b633-613e-4c25-8939-35f147e9d113.txt"}, "2": {"N": None, "a": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/38aade4e-03b4-4f73-aaf6-3ab87289a032.txt", "c": None, "d": 1567640986, "e": None, "f": ["adder", "assumeflag"], "j": None, "n": None, "p": None, "t": [1, 6, 5, 1, 0, "83.33333", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/791886122b02a2e52e5dd09e8be5f92e09e83f0b/38aade4e-03b4-4f73-aaf6-3ab87289a032.txt"}}}
    commit_base = CommitFactory.create(
        message='test_compare_commits_base',
        commitid='791886122b02a2e52e5dd09e8be5f92e09e83f0b',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
        report=commit_base_report
    )
    commit_head_report = {"files": {"src/adder/adders.py": [4, [0, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0], [[0, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0], [0, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0]], [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0]], "tests/unit/test_main.py": [1, [0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 4, 4, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], "src/subtractor/subtractor.py": [3, [0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 9, 1, 0, "90.00000", 0, 0, 0, 0, 0, 0, 0]], None], "tests/unit/adder/test_adder.py": [0, [0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 6, 6, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 1, 1, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], "tests/unit/subtractor/test_subtractor.py": [2, [0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0], [[0, 10, 10, 0, 0, "100", 0, 0, 0, 0, 0, 0, 0]], [0, 0, 0, 0, 0, None, 0, 0, 0, 0, None, None, 0]]}, "sessions": {"0": {"N": None, "a": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/34a07c58-56e0-41aa-b319-324d96478c13.txt", "c": None, "d": 1567016331, "e": None, "f": None, "j": None, "n": None, "p": None, "t": [5, 38, 36, 2, 0, "94.73684", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-08-28/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/34a07c58-56e0-41aa-b319-324d96478c13.txt"}, "1": {"N": None, "a": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/d7152163-f3d7-4347-8834-6f8e45effb0b.txt", "c": None, "d": 1567641020, "e": None, "f": ["adder", "assumeflag"], "j": None, "n": None, "p": None, "t": [1, 8, 7, 1, 0, "87.50000", 0, 0, 0, 0, 0, 0, 0], "u": None, "storage_path": "v4/raw/2019-09-04/4A3A4B0C7B00EAEA3F77AA7EB90BE4AB/f64b22e6af4bbe3917ac4a7c346feb03493c2b67/d7152163-f3d7-4347-8834-6f8e45effb0b.txt"}}}
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
        report=commit_with_change_report
    )
    client.force_login(user=repo.author)
    return repo, commit_base, commit_head, file_change_commit
