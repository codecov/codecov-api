import json
from unittest.mock import patch


from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory, BranchFactory


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
        commit_head = CommitFactory.create(
            message='test_compare_commits_head',
            commitid='d8d9ce1a4c54a443607a2cc14cdeefc4dca4fde9',
            parent_commit_id=parent_commit.commitid,
            repository=repo,
        )
        branch_base = BranchFactory.create(head=commit_base, repository=commit_base.repository)
        branch_head = BranchFactory.create(head=commit_head, repository=commit_head.repository)
        git_commits = [
            {
                'commitid': commit_base.commitid,
                'message': commit_base.message,
                'timestamp': '2019-03-31T02:28:02Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
            {
                'commitid': 'e8d9ce1a4c54a443607a2dd14cdeefc4dca4fde8',
                'message': 'Some commit that doesnt have an upload',
                'timestamp': '2019-03-31T04:28:02Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
            {
                'commitid': commit_head.commitid,
                'message': commit_head.message,
                'timestamp': '2019-03-31T07:23:19Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
        ]
        mocked_comparison.return_value = {
            'diff': {
                'files': [
                    {
                        'lines': [
                            [1, 1, None, [[0, 1, None, None, None]], None, None],
                            [4, 1, None, [[0, 1, None, None, None]], None, None],
                            [5, 0, None, [[0, 0, None, None, None]], None, None]],
                        'name': 'tests/__init__.py',
                        'totals': {
                            'branches': 0, 'complexity': 0, 'complexity_total': 0,
                            'coverage': '66.66667', 'diff': 0, 'files': 0, 'hits': 2,
                            'lines': 3, 'messages': 0, 'methods': 0, 'misses': 1,
                            'partials': 0, 'sessions': 0
                        }
                    }
                ]
            },
            'commits': git_commits
        }
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
        commit_head = CommitFactory.create(
            message='test_compare_commits_head',
            commitid='d8d9ce1a4c54a443607a2cc14cdeefc4dca4fde9',
            parent_commit_id=parent_commit.commitid,
            repository=repo,
        )
        git_commits = [
            {
                'commitid': commit_base.commitid,
                'message': commit_base.message,
                'timestamp': '2019-03-31T02:28:02Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
            {
                'commitid': 'e8d9ce1a4c54a443607a2dd14cdeefc4dca4fde8',
                'message': 'Some commit that doesnt have an upload',
                'timestamp': '2019-03-31T04:28:02Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
            {
                'commitid': commit_head.commitid,
                'message': commit_head.message,
                'timestamp': '2019-03-31T07:23:19Z',
                'author': {
                    'id': self.user.ownerid,
                    'username': self.user.username,
                    'name': self.user.name,
                    'email': self.user.email
                }
            },
        ]
        mocked_comparison.return_value = {
            'diff': {
                'files': [
                    {
                        'lines': [
                            [1, 1, None, [[0, 1, None, None, None]], None, None],
                            [4, 1, None, [[0, 1, None, None, None]], None, None],
                            [5, 0, None, [[0, 0, None, None, None]], None, None]],
                        'name': 'tests/__init__.py',
                        'totals': {
                            'branches': 0, 'complexity': 0, 'complexity_total': 0,
                            'coverage': '66.66667', 'diff': 0, 'files': 0, 'hits': 2,
                            'lines': 3, 'messages': 0, 'methods': 0, 'misses': 1,
                            'partials': 0, 'sessions': 0
                        }
                    }
                ]
            },
            'commits': git_commits
        }
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

