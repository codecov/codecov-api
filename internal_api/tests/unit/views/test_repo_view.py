from unittest.mock import patch

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


@patch("internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoViewTest(InternalAPITest):
    def setUp(self):
        org = OwnerFactory(username='codecov', service='github')

        self.repo1 = RepositoryFactory(author=org, active=True, private=True, name='repo1')
        self.repo2 = RepositoryFactory(author=org, active=True, private=True, name='repo2')
        self.repo3 = RepositoryFactory(author=org, name='repo3')

        repos_with_permission = [
            self.repo1.repoid,
            self.repo2.repoid,
            self.repo3.repoid,
        ]

        self.user = OwnerFactory(
            username='codecov-user',
            service='github',
            organizations=[org.ownerid],
            permission=repos_with_permission
        )

        RepositoryFactory(author=OwnerFactory(), active=True)
        pass

    def test_get_active_repos(self, mock_provider):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos?active=True')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 2, "got the wrong number of repos: {}".format(content['results']))

    def test_get_inactive_repos(self, mock_provider):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos?active=False')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 1, "got the wrong number of repos: {}".format(content['results']))

    def test_get_all_repos(self, mock_provider):
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repos')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(len(content['results']), 3, "got the wrong number of repos: {}".format(content['results']))

    def test_repo_details_with_permissions(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repo1/details')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        assert 'upload_token' in content

    def test_repo_details_without_write_permissions(self, mock_provider):
        mock_provider.return_value = True, False
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repo1/details')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        assert not content['can_edit']
        assert 'upload_token' not in content

    def test_repo_details_without_read_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get('/internal/codecov/repo1/details')
        self.assertEqual(response.status_code, 403)

    def test_repo_regenerate_upload_token(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.patch('/internal/codecov/repo1/regenerate-upload-token', data={}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        assert content['upload_token'] is not self.repo1.upload_token

    def test_repo_regenerate_upload_token_not_allowed(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.patch('/internal/codecov/repo1/regenerate-upload-token', data={}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        content = self.json_content(response)
        assert 'upload_token' not in content
