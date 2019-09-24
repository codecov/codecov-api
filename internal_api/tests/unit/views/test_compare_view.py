import json
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings

from rest_framework import status
from rest_framework.reverse import reverse


from archive.services import ArchiveService
from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from compare.services import Comparison
from core.tests.factories import (
    RepositoryFactory,
    CommitFactory,
    BranchFactory,
    PullFactory,
)

current_file = Path(__file__)


class TestCompareCommitsView(InternalAPITest):

    def setUp(self):
        org = OwnerFactory(username='Codecov')
        self.user = OwnerFactory(username='codecov-user',
                                 email='codecov-user@codecov.io',
                                 organizations=[org.ownerid])
        self.repo = RepositoryFactory(author=self.user)

        self.client.force_login(user=self.user)

    def _get_commits_comparison(self, kwargs, query_params):
        return self.client.get(reverse('compare-commits', kwargs=kwargs), data=query_params)

    def test_compare_commits_bad_commit(self):
        parent_commit = CommitFactory.create(
            message='test_compare_commits_parent',
            commitid='c5b6730',
            repository=self.repo,
        )
        commit_base = CommitFactory.create(
            message='test_compare_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            parent_commit_id=parent_commit.commitid,
            repository=self.repo,
        )

        bad_commitid = "9193232a8fe3429496123ba82b5fed2583d1b5eb"
        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": commit_base.commitid,
                "head": bad_commitid
            }
        )
        assert response.status_code == 404

    def test_compare_commits_bad_branch(self):
        parent_commit = CommitFactory.create(
            message='test_compare_commits_parent',
            commitid='c5b6730',
            repository=self.repo,
        )
        commit_base = CommitFactory.create(
            message='test_compare_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            parent_commit_id=parent_commit.commitid,
            repository=self.repo,
        )

        bad_branch = "bad-branch"
        branch_base = BranchFactory.create(
            head=commit_base,
            repository=self.repo
        )
        response = self._get_commits_comparison(
            kwargs={
                "orgName": self.repo.author.username,
                "repoName": self.repo.name
            },
            query_params={
                "base": branch_base.name,
                "head": bad_branch
            }
        )
        assert response.status_code == 404

    @patch("compare.services.Comparison._calculate_git_comparison")
    def test_compare_commits_view_with_branchname(self, mocked_comparison):
        repo, commit_base, commit_head = build_commits(client=self.client)
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, self.user, commit_base, commit_head)
        branch_base = BranchFactory.create(head=commit_base, repository=commit_base.repository)
        branch_head = BranchFactory.create(head=commit_head, repository=commit_head.repository)

        response = self._get_commits_comparison(
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "base": branch_base.name,
                "head": branch_head.name
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == git_commits
        assert content['commit_uploads'][0]['commitid'] == commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == commit_head.totals
        assert content['commit_uploads'][1]['commitid'] == commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == commit_base.totals

    @patch("compare.services.Comparison._calculate_git_comparison")
    def test_compare_commits_view_with_commitid(self, mocked_comparison):
        repo, commit_base, commit_head = build_commits(client=self.client)
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, self.user, commit_base, commit_head)

        response = self._get_commits_comparison(
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "base": commit_base.commitid,
                "head": commit_head.commitid
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == git_commits
        assert content['commit_uploads'][0]['commitid'] == commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == commit_head.totals
        assert content['commit_uploads'][1]['commitid'] == commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == commit_base.totals

    @patch("compare.services.Comparison._calculate_git_comparison")
    def test_compare_commits_view_with_pullid(self, mocked_comparison):
        repo, base, head = build_commits(self.client)

        pull = PullFactory(
            pullid=2,
            repository=repo,
            author=repo.author,
            base=base,
            head=head
        )

        git_commits, _ = build_mocked_compare_commits(
            mocked_comparison,
            pull.repository.author,
            pull.base,
            pull.head
        )

        response = self._get_commits_comparison(
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "pullid": pull.pullid
            }
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assert response.data['git_commits'] == git_commits
        assert response.data['commit_uploads'][0]['commitid'] == head.commitid
        assert response.data['commit_uploads'][0]['totals'] == head.totals
        assert response.data['commit_uploads'][1]['commitid'] == base.commitid
        assert response.data['commit_uploads'][1]['totals'] == base.totals


class TestCompareDetailsView(object):

    def _get_compare_details(self, client, kwargs, query_params):
        return client.get(reverse('compare-details', kwargs=kwargs), data=query_params)

    def verify_details_output(self, response, expected_report_result, git_commits):
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['head_report']['totals'] == expected_report_result['totals']
        assert content['head_report']['files'][0]['name'] == expected_report_result['files'][0]['name']
        assert 'lines' in content['head_report']['files'][0]
        assert 'git_commits' in content
        assert content['base_commit'] == git_commits[0]['commitid']
        assert content['head_commit'] == git_commits[-1]['commitid']
        assert content['git_commits'] == git_commits

    @override_settings(DEBUG=True)
    def test_compare_details_view(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        org = OwnerFactory(username='Codecov')
        user = OwnerFactory(username='codecov-user',
                            email='codecov-user@codecov.io',
                            organizations=[org.ownerid])
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, user, commit_base, commit_head)

        response = self._get_compare_details(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "base": commit_base.commitid,
                "head": commit_head.commitid
            }
        )

        self.verify_details_output(response, expected_report_result, git_commits)

    @override_settings(DEBUG=True)
    def test_compare_details_accepts_pullid_query_param(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, repo.author, commit_base, commit_head)

        response = self._get_compare_details(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "pullid": PullFactory(
                    base=commit_base,
                    head=commit_head,
                    pullid=2,
                    author=commit_head.author,
                    repository=repo
                ).pullid
            }
        )

        self.verify_details_output(response, expected_report_result, git_commits)


class TestCompareSingleFileDiffView:
    def _get_single_file_diff(self, client, kwargs, query_params):
        return client.get(reverse('compare-diff-file', kwargs=kwargs), data=query_params)

    @override_settings(DEBUG=True)
    def test_compare_single_file_diff_view(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        build_mocked_compare_commits(mocked_comparison, repo.author, commit_base, commit_head)

        response = self._get_single_file_diff(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name,
                "file_path": "src/adder/adder.py"
            },
            query_params={
                "head": commit_head.commitid,
                "base": commit_base.commitid
            }
        )

        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert 'src_diff' in content
        assert content['src_diff'] == {
            "type": "modified",
            "before": None,
            "segments": [
                {
                    "header": [
                        "9",
                        "3",
                        "9",
                        "6"
                    ],
                    "lines": [
                        "         ",
                        "     def multiply(self, x, y):",
                        "         return x * y",
                        "+    ",
                        "+    def double(self, x):",
                        "+        return 2 * x"
                    ]
                }
            ],
            "stats": {
                "added": 3,
                "removed": 0
            }
        }
        assert 'base_coverage' in content
        assert 'head_coverage' in content


class TestCompareFullSrcView:
    def _get_compare_src(self, client, kwargs, query_params):
        return client.get(reverse('compare-src-full', kwargs=kwargs), data=query_params)

    def verify_src_output(self, response, expected_report_result):
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert 'src_diff' in content

    @override_settings(DEBUG=True)
    def test_basic_return_with_commit_refs(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        git_commits, src_diff = build_mocked_compare_commits(
            mocked_comparison,
            repo.author,
            commit_base,
            commit_head
        )

        response = self._get_compare_src(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "base": commit_base.commitid,
                "head": commit_head.commitid
            }
        )

        self.verify_src_output(response, expected_report_result)

    @override_settings(DEBUG=True)
    def test_accepts_pullid_query_param(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        git_commits, src_diff = build_mocked_compare_commits(
            mocked_comparison,
            repo.author,
            commit_base,
            commit_head
        )

        response = self._get_compare_src(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "pullid": PullFactory(
                    base=commit_base,
                    head=commit_head,
                    pullid=2,
                    author=commit_head.author,
                    repository=commit_head.repository
                ).pullid
            }
        )

        self.verify_src_output(response, expected_report_result)

    @override_settings(DEBUG=True)
    def test_omits_line_data_after_first_five_files(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        git_commits, src_diff = build_mocked_compare_commits(
            mocked_comparison,
            repo.author,
            commit_base,
            commit_head
        )

        # Make src_diff long enough to trigger line data omission
        # I'm just adding copies of 'main.py' with dummy names
        src_diff["files"] = src_diff["files"]
        for i in range(5):
            # using json library to deep-copy the dict,
            # but there might be a better way
            src_diff["files"][f"main{i}.py"] = json.loads(
                json.dumps(src_diff["files"]["src/main.py"])
            )

        assert len(mocked_comparison.return_value["diff"]["files"]) > 5

        response = self._get_compare_src(
            client,
            kwargs={
                "orgName": repo.author.username,
                "repoName": repo.name
            },
            query_params={
                "head": commit_head.commitid,
                "base": commit_base.commitid
            }
        )

        # there should be exactly five files with a non-empty list for "lines"
        files_with_lines = 0
        content = json.loads(response.content.decode())
        for _, diff_data in content["src_diff"]["files"].items():
            if diff_data["segments"][0]["lines"]:
                files_with_lines += 1

        assert files_with_lines == 5


def build_commits(client):
    """
        build commits in mock_db that are based on a real git commit for using VCR
    :param user:
    :param client:
    :return: repo, commit_base, commit_head
    """
    repo = RepositoryFactory.create(
        author__unencrypted_oauth_token='testqmit3okrgutcoyzscveipor3toi3nsmb927v',
        author__username='ThiagoCodecov'
    )
    parent_commit = CommitFactory.create(
        message='test_compare_parent',
        commitid='c5b6730',
        repository=repo,
    )
    commit_base = CommitFactory.create(
        message='test_compare_commits_base',
        commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    commit_head = CommitFactory.create(
        message='test_compare_commits_head',
        commitid='abf6d4df662c47e32460020ab14abf9303581429',
        parent_commit_id=parent_commit.commitid,
        repository=repo,
    )
    client.force_login(user=repo.author)
    return repo, commit_base, commit_head


def build_mocked_report_archive(mocker):
    mocked = mocker.patch.object(ArchiveService, 'read_chunks')
    f = open(
        current_file.parent.parent.parent.parent.parent / 'archive/tests/samples' / 'chunks.txt',
        'r'
    )
    mocker.patch.object(ArchiveService, 'create_root_storage')
    mocked.return_value = f.read()

    expected_report_result = {
        'files': [
            ({
                'name': 'tests/__init__.py',
                'lines': [
                    (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (4, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (5, 0, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None)
                ],
                'totals': {
                    'files': 0,
                    'lines': 3,
                    'hits': 2,
                    'misses': 1,
                    'partials': 0,
                    'coverage': '66.66667',
                    'branches': 0,
                    'methods': 0,
                    'messages': 0,
                    'sessions': 0,
                    'complexity': 0,
                    'complexity_total': 0,
                    'diff': 0
                }
            }),
            ({
                'name': 'awesome/__init__.py',
                'lines': [
                    (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (2, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (5, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None),
                    (6, 1, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None),
                    (9, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (10, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (11, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (12, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (15, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (16, 0, None, [[0, 0, None, None, None], [1, 0, None, None, None]], None, None)
                ],
                'totals': {
                    'files': 0,
                    'lines': 10,
                    'hits': 8,
                    'misses': 2,
                    'partials': 0,
                    'coverage': '80.00000',
                    'branches': 0,
                    'methods': 0,
                    'messages': 0,
                    'sessions': 0,
                    'complexity': 0,
                    'complexity_total': 0,
                    'diff': 0
                }
            }),
            ({
                'name': 'tests/test_sample.py',
                'lines': [
                    (1, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (4, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (5, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (8, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (9, 1, None, [[0, 1, None, None, None], [1, 0, None, None, None]], None, None),
                    (12, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None),
                    (13, 1, None, [[0, 1, None, None, None], [1, 1, None, None, None]], None, None)
                ],
                'totals': {
                    'files': 0,
                    'lines': 7,
                    'hits': 7,
                    'misses': 0,
                    'partials': 0,
                    'coverage': '100',
                    'branches': 0,
                    'methods': 0,
                    'messages': 0,
                    'sessions': 0,
                    'complexity': 0,
                    'complexity_total': 0,
                    'diff': 0
                }
            })
        ],
        'totals': {
            'files': 3,
            'lines': 20,
            'hits': 17,
            'misses': 3,
            'partials': 0,
            'coverage': '85.00000',
            'branches': 0,
            'methods': 0,
            'messages': 0,
            'sessions': 1,
            'complexity': 0,
            'complexity_total': 0,
            'diff': [1, 2, 1, 1, 0, '50.00000', 0, 0, 0, 0, 0, 0, 0]
        }
    }
    return expected_report_result


def build_mocked_compare_commits(mocked_comparison, user, commit_base, commit_head):
    """

    :param mocked_comparison:
    :param user:
    :param client:
    :return: repo, commit_base, commit_head, git_commits, src_diff
    """
    git_commits = [
        {
            'commitid': commit_base.commitid,
            'message': commit_base.message,
            'timestamp': '2019-03-31T02:28:02Z',
            'author': {
                'id': user.ownerid,
                'username': user.username,
                'name': user.name,
                'email': user.email
            }
        },
        {
            'commitid': 'e8d9ce1a4c54a443607a2dd14cdeefc4dca4fde8',
            'message': 'Some commit that doesnt have an upload',
            'timestamp': '2019-03-31T04:28:02Z',
            'author': {
                'id': user.ownerid,
                'username': user.username,
                'name': user.name,
                'email': user.email
            }
        },
        {
            'commitid': commit_head.commitid,
            'message': commit_head.message,
            'timestamp': '2019-03-31T07:23:19Z',
            'author': {
                'id': user.ownerid,
                'username': user.username,
                'name': user.name,
                'email': user.email
            }
        },
    ]
    src_diff = {
        "files": {
            "src/adder/adder.py": {
                "type": "modified",
                "before": None,
                "segments": [
                    {
                        "header": [
                            "9",
                            "3",
                            "9",
                            "6"
                        ],
                        "lines": [
                            "         ",
                            "     def multiply(self, x, y):",
                            "         return x * y",
                            "+    ",
                            "+    def double(self, x):",
                            "+        return 2 * x"
                        ]
                    }
                ],
                "stats": {
                    "added": 3,
                    "removed": 0
                }
            },
            "src/main.py": {
                "type": "modified",
                "before": None,
                "segments": [
                    {
                        "header": [
                            "10",
                            "7",
                            "10",
                            "8"
                        ],
                        "lines": [
                            "     product = Adder().multiply(x,y)",
                            "     quotient = Subtractor().divide(x,y)",
                            "     fraction = Subtractor().fractionate(x)",
                            "-    print(\"Given: {} and {}. The sum: {}. The difference: {}. The product: {}. The quotient: {}. The fraction: {}\").format(x, y, sum, diff, product, quotient, fraction)",
                            "+    double = Adder().double(x)",
                            "+    print(\"Given: {} and {}. The sum: {}. The difference: {}. The product: {}. The quotient: {}. The fraction: {}. The double of x: {}\").format(x, y, sum, diff, product, quotient, fraction, double)",
                            " ",
                            " ",
                            " if __name__ == \"__main__\":"
                        ]
                    }
                ],
                "stats": {
                    "added": 2,
                    "removed": 1
                }
            }
        }
    }
    mocked_comparison.return_value = {
        'diff': src_diff,
        'commits': git_commits
    }
    return git_commits, src_diff
