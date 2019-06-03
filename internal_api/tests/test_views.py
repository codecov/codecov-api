import json

from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


class OrgsViewTest(TestCase):

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


class RepoViewTest(TestCase):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')
        # Create different types of repos
        repo_with_permission = [RepositoryFactory(author=org, active=True).repoid,
                                RepositoryFactory(author=org, active=True).repoid,
                                RepositoryFactory(author=org).repoid]
        self.user = OwnerFactory(username='codecov-user',
                                 service='github',
                                 organizations=[org.ownerid],
                                 permission=repo_with_permission)
        RepositoryFactory(author=OwnerFactory(), active=True)
        pass

    def test_get_active_repos(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos?active=True')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of repos: {}".format(content['results']))

    def test_get_inactive_repos(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos?active=False')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 1, "got the wrong number of repos: {}".format(content['results']))

    def test_get_all_repos(self):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos')
        self.assertEqual(response.status_code, 200)
        content = json_content(response)
        self.assertEqual(len(content['results']), 3, "got the wrong number of repos: {}".format(content['results']))


def json_content(response):
    return json.loads(response.content.decode())