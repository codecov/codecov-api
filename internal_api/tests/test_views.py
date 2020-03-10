import json
from unittest.mock import patch

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, PullFactory, CommitFactory, BranchFactory
from core.models import Pull

from rest_framework.reverse import reverse
from rest_framework import status

get_permissions_method = "internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions"


class OrgsViewTest(InternalAPITest):

    def setUp(self):
        org = OwnerFactory(username='Codecov')
        RepositoryFactory(author=org)
        self.user = OwnerFactory(username='codecov-user',
                                 organizations=[org.ownerid])
        RepositoryFactory(author=self.user)
        pass

    def test_get_orgs_for_valid_user(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/profile')
        self.assertEqual(response.status_code, 200)

    def test_get_orgs_for_invalid_user(self):
        response = self.client.get('/internal/profile')
        self.assertEqual(response.status_code, 403)


@patch(get_permissions_method)
class RepoPullList(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / pulls
        self.repo = RepositoryFactory(author=self.org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(
            author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [self.repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[self.org.ownerid],
                                 permission=repo_with_permission)
        PullFactory(
            pullid=10,
            author=self.org,
            repository=self.repo,
            state='open',
            head=CommitFactory(
                repository=self.repo,
                author=self.user
            ).commitid,
            base=CommitFactory(
                repository=self.repo,
                author=self.user
            ).commitid
        )
        PullFactory(pullid=11, author=self.org, repository=self.repo, state='closed')
        PullFactory(pullid=12, author=other_org, repository=other_repo)
        self.correct_kwargs={'orgName':'codecov', 'repoName':'testRepoName'}
        self.incorrect_kwargs={'orgName':'codecov', 'repoName':'otherRepoName'}

    def test_get_pulls(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(reverse('pulls-list', kwargs=self.correct_kwargs))
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of pulls: {}".format(
            content['results']))

    def test_get_pulls_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get(reverse('pulls-list', kwargs=self.correct_kwargs))
        self.assertEqual(response.status_code, 403)

    def test_get_pulls_filter_state(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(reverse('pulls-list', kwargs=self.correct_kwargs), data={'state': 'open'})
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 1, "got the wrong number of open pulls: {}".format(
            content['results']))

    def test_get_pull_wrong_org(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(reverse('pulls-list', kwargs=self.incorrect_kwargs))
        content = self.json_content(response)
        self.assertEqual(response.status_code, 404,
                         "got unexpected response: {}".format(content))

    def test_get_pulls_null_head_author_doesnt_crash(self, mock_provider):
        mock_provider.return_value = True, True
        new_owner = OwnerFactory()

        PullFactory(
            pullid=13,
            author=self.org,
            repository=self.repo,
            state='open',
            head=CommitFactory(
                repository=self.repo,
                author=new_owner
            ).commitid,
            base=CommitFactory(
                repository=self.repo,
                author=new_owner
            ).commitid
        )

        new_owner.delete()

        self.client.force_login(user=self.user)
        response = self.client.get(reverse('pulls-list', kwargs=self.correct_kwargs))
        assert response.status_code == status.HTTP_200_OK


@patch(get_permissions_method)
class RepoPullDetail(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / pulls
        repo = RepositoryFactory(author=org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(
            author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        PullFactory(pullid=10, author=org, repository=repo, state='open')
        PullFactory(pullid=11, author=org, repository=repo, state='closed')

    def test_get_pull(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/pulls/10/')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(content['pullid'], 10)

    def test_get_pull_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/pulls/10/')
        self.assertEqual(response.status_code, 403)

@patch(get_permissions_method)
class RepoCommitList(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / commits
        repo = RepositoryFactory(author=org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(
            author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        CommitFactory(author=org, repository=repo)
        CommitFactory(author=org, repository=repo)
        CommitFactory(author=other_org, repository=other_repo)

    def test_get_commits(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/commits')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of commits: {}".format(
            content['results']))

    def test_get_commits_wrong_org(self, mock_provider):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/otherRepoName/commits')
        content = self.json_content(response)
        self.assertEqual(response.status_code, 404,
                         "got unexpected response: {}".format(content))

    def test_filters_by_branch_name(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        repo = RepositoryFactory(author=self.user, active=True, private=True, name='banana')
        CommitFactory.create(
            message='test_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5ec',
            repository=repo,
        )
        commit_non_master = CommitFactory.create(
            message='another_commit_not_on_master',
            commitid='ddcc232a8fe3429496956ba82b5fed2583d1b5ec',
            repository=repo,
            branch="other-branch"
        )

        response = self.client.get('/internal/codecov-user/banana/commits')
        content = json.loads(response.content.decode())
        assert len(content['results']) == 2
        assert content['results'][0]['commitid'] == commit_non_master.commitid

        response = self.client.get('/internal/codecov-user/banana/commits?branch=other-branch')
        content = json.loads(response.content.decode())
        assert len(content['results']) == 1
        assert content['results'][0]['commitid'] == commit_non_master.commitid


@patch(get_permissions_method)
class RepoBranchList(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / branches
        repo = RepositoryFactory(
            author=org, name='testRepoName', active=True, private=True)
        commit = CommitFactory(repository=repo)
        other_repo = RepositoryFactory(
            author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        BranchFactory(authors=[org.ownerid], repository=repo, head=commit.commitid)
        BranchFactory(authors=[org.ownerid], repository=repo, head=commit.commitid)
        BranchFactory(authors=[other_org.ownerid], repository=other_repo)

    def test_get_branches(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/branches')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of pulls: {}".format(
            content['results']))

    def test_get_branches_without_permission(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/branches')
        self.assertEqual(response.status_code, 403)

    def test_get_branches_wrong_org(self, mock_provider):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/otherRepoName/branches')
        content = self.json_content(response)
        self.assertEqual(response.status_code, 404,
                         "got unexpected response: {}".format(content))
