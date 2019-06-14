import json

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, PullFactory, CommitFactory, BranchFactory


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
        response = self.client.get('/internal/orgs')
        self.assertEqual(response.status_code, 200)

    def test_get_orgs_for_invalid_user(self):
        response = self.client.get('/internal/orgs')
        self.assertEqual(response.status_code, 403)


class RepoPullList(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / pulls
        repo = RepositoryFactory(author=org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        PullFactory(pullid=10, author=org, repository=repo, state='open')
        PullFactory(pullid=11, author=org, repository=repo, state='closed')
        PullFactory(pullid=12, author=other_org, repository=other_repo)
        pass

    def test_get_pulls(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/pulls')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of pulls: {}".format(content['results']))

    def test_get_pulls_filter_state(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/pulls?state=open')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 1, "got the wrong number of open pulls: {}".format(content['results']))

    def test_get_pull_wrong_org(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/otherRepoName/pulls')
        content = json_content(response)
        self.assertEqual(response.status_code, 404, "got unexpected response: {}".format(content))


class RepoCommitList(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / commits
        repo = RepositoryFactory(author=org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        CommitFactory(author=org, repository=repo)
        CommitFactory(author=org, repository=repo)
        CommitFactory(author=other_org, repository=other_repo)
        pass

    def test_get_commits(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/commits')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of commits: {}".format(content['results']))

    def test_get_commits_wrong_org(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/otherRepoName/commits')
        content = json_content(response)
        self.assertEqual(response.status_code, 404, "got unexpected response: {}".format(content))


class RepoBranchList(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        other_org = OwnerFactory(username='other_org')
        # Create different types of repos / branches
        repo = RepositoryFactory(author=org, name='testRepoName', active=True)
        other_repo = RepositoryFactory(author=other_org, name='otherRepoName', active=True)
        repo_with_permission = [repo.repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        BranchFactory(authors=[org.ownerid], repository=repo)
        BranchFactory(authors=[org.ownerid], repository=repo)
        BranchFactory(authors=[other_org.ownerid], repository=other_repo)
        pass

    def test_get_branches(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/testRepoName/branches')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of pulls: {}".format(content['results']))

    def test_get_branches_wrong_org(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/otherRepoName/branches')
        content = json_content(response)
        self.assertEqual(response.status_code, 404, "got unexpected response: {}".format(content))


def json_content(response):
    return json.loads(response.content.decode())
