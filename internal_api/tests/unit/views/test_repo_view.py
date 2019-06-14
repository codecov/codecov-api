from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from internal_api.tests.test_views import json_content


class RepoViewTest(InternalAPITest):
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

