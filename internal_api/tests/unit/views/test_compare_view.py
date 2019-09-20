import json
from pathlib import Path
from unittest.mock import patch

from django.test import override_settings

from archive.services import ArchiveService
from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from compare.services import Comparison
from core.tests.factories import RepositoryFactory, CommitFactory, BranchFactory

current_file = Path(__file__)


class TestCompareCommitsView(InternalAPITest):

    def setUp(self):
        org = OwnerFactory(username='Codecov')
        RepositoryFactory(author=org)
        self.user = OwnerFactory(username='codecov-user',
                                 email='codecov-user@codecov.io',
                                 organizations=[org.ownerid])
        pass

    def test_compare_commits_bad_commit(self):
        self.client.force_login(user=self.user)
        repo = RepositoryFactory(author=self.user)
        parent_commit = CommitFactory.create(
            message='test_compare_commits_parent',
            commitid='c5b6730',
            repository=repo,
        )
        commit_base = CommitFactory.create(
            message='test_compare_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            parent_commit_id=parent_commit.commitid,
            repository=repo,
        )
        bad_commitid = "9193232a8fe3429496123ba82b5fed2583d1b5eb"
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{bad_commitid}/commits'
        print("request url: ", url)
        response = self.client.get(url)
        assert response.status_code == 404

    def test_compare_commits_bad_branch(self):
        self.client.force_login(user=self.user)
        repo = RepositoryFactory(author=self.user)
        parent_commit = CommitFactory.create(
            message='test_compare_commits_parent',
            commitid='c5b6730',
            repository=repo,
        )
        commit_base = CommitFactory.create(
            message='test_compare_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            parent_commit_id=parent_commit.commitid,
            repository=repo,
        )
        bad_branch = "bad-branch"
        branch_base = BranchFactory.create(head=commit_base, repository=commit_base.repository)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{branch_base.name}...{bad_branch}/commits'
        print("request url: ", url)
        response = self.client.get(url)
        assert response.status_code == 404

    @patch("compare.services.Comparison._calculate_git_comparison")
    def test_compare_commits_view_with_branchname(self, mocked_comparison):
        repo, commit_base, commit_head = build_commits(client=self.client)
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, self.user, commit_base, commit_head)
        branch_base = BranchFactory.create(head=commit_base, repository=commit_base.repository)
        branch_head = BranchFactory.create(head=commit_head, repository=commit_head.repository)

        url = f'/internal/{repo.author.username}/{repo.name}/compare/{branch_base.name}...{branch_head.name}/commits'
        print("request url: ", url)
        response = self.client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == git_commits
        print("this is the response: ", content)
        assert content['commit_uploads'][0]['commitid'] == commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == commit_head.totals
        assert content['commit_uploads'][1]['commitid'] == commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == commit_base.totals

    @patch("compare.services.Comparison._calculate_git_comparison")
    def test_compare_commits_view_with_commitid(self, mocked_comparison):
        repo, commit_base, commit_head = build_commits(client=self.client)
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, self.user, commit_base, commit_head)

        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/commits'
        print("request url: ", url)
        response = self.client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['git_commits'] == git_commits
        print("this is the response: ", content)
        assert content['commit_uploads'][0]['commitid'] == commit_head.commitid
        assert content['commit_uploads'][0]['totals'] == commit_head.totals
        assert content['commit_uploads'][1]['commitid'] == commit_base.commitid
        assert content['commit_uploads'][1]['totals'] == commit_base.totals


class TestCompareDetailsView(object):

    @override_settings(DEBUG=True)
    def test_compare_details_view(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/details'
        print("request url: ", url)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        org = OwnerFactory(username='Codecov')
        user = OwnerFactory(username='codecov-user',
                            email='codecov-user@codecov.io',
                            organizations=[org.ownerid])
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, user, commit_base, commit_head)
        response = client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['head_report']['totals'] == expected_report_result['totals']
        assert content['head_report']['files'][0]['name'] == expected_report_result['files'][0]['name']
        assert 'lines' not in content['head_report']['files'][0]
        assert 'git_commits' in content
        assert content['base_commit'] == commit_base.commitid
        assert content['head_commit'] == commit_head.commitid
        assert content['git_commits'] == git_commits

    @override_settings(DEBUG=True)
    def test_compare_line_coverage_withsrc_view(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        expected_report_result = build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        git_commits, src_diff = build_mocked_compare_commits(mocked_comparison, repo.author, commit_base, commit_head)

        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/src'
        print("request url: ", url)
        response = client.get(url)
        assert response.status_code == 200
        content = json.loads(response.content.decode())
        assert content['head_report']['totals'] == expected_report_result['totals']
        assert content['head_report']['files'][0]['name'] == expected_report_result['files'][0]['name']
        assert 'lines' in content['head_report']['files'][0]
        assert 'src_diff' in content

    @override_settings(DEBUG=True)
    def test_compare_single_file_diff_view(self, mocker, db, client, codecov_vcr):
        repo, commit_base, commit_head = build_commits(client=client)
        build_mocked_report_archive(mocker)
        mocked_comparison = mocker.patch.object(Comparison, '_calculate_git_comparison')
        build_mocked_compare_commits(mocked_comparison, repo.author, commit_base, commit_head)

        url = f'/internal/{repo.author.username}/{repo.name}/compare/{commit_base.commitid}...{commit_head.commitid}/diff_file/src/adder/adder.py'
        print("request url: ", url)
        response = client.get(url)
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