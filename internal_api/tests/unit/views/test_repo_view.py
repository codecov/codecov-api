from unittest.mock import patch
import json

from rest_framework.reverse import reverse

from covreports.utils.tuples import ReportTotals
from django.test import override_settings

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
from internal_api.repo.repository_accessors import RepoAccessors
from internal_api.tests.unit.views.test_compare_view import build_mocked_report_archive


@patch("internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class TestRepositoryListView(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory(username='codecov', service='github')

        self.repo1 = RepositoryFactory(author=self.org, active=True, private=True, name='A')
        self.repo2 = RepositoryFactory(author=self.org, active=True, private=True, name='B')

        repos_with_permission = [
            self.repo1.repoid,
            self.repo2.repoid,
        ]

        self.user = OwnerFactory(
            username='codecov-user',
            service='github',
            organizations=[self.org.ownerid],
            permission=repos_with_permission
        )

        self.client.force_login(user=self.user)

    def _get_repos(self, query_params):
        return self.client.get(
            reverse('repos-list', kwargs={"orgName": self.org.username}),
            data=query_params
        )

    def test_order_by_updatestamp(self, _):
        response = self._get_repos(query_params={'ordering': 'updatestamp'})

        assert response.data["results"][0]["repoid"] == self.repo1.repoid
        assert response.data["results"][1]["repoid"] == self.repo2.repoid

        reverse_response = self._get_repos(query_params={'ordering': '-updatestamp'})

        assert reverse_response.data["results"][0]["repoid"] == self.repo2.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo1.repoid

    def test_order_by_name(self, _):
        response = self._get_repos(query_params={'ordering': 'name'})

        assert response.data["results"][0]["repoid"] == self.repo1.repoid
        assert response.data["results"][1]["repoid"] == self.repo2.repoid

        reverse_response = self._get_repos(query_params={'ordering': '-name'})

        assert reverse_response.data["results"][0]["repoid"] == self.repo2.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo1.repoid

    @patch("archive.services.ArchiveService.create_root_storage")
    @patch("archive.services.ArchiveService.read_chunks")
    def test_order_by_coverage(self, read_chunks_mock, *args):
        read_chunks_mock.return_value = []

        CommitFactory(repository=self.repo1, totals={"c": 25})
        CommitFactory(repository=self.repo1, totals={"c": 41})
        CommitFactory(repository=self.repo2, totals={"c": 32})

        response = self._get_repos(query_params={'ordering': 'coverage'})

        assert response.data["results"][0]["repoid"] == self.repo2.repoid
        assert response.data["results"][1]["repoid"] == self.repo1.repoid

        reverse_response = self._get_repos(query_params={'ordering': '-coverage'})

        assert reverse_response.data["results"][0]["repoid"] == self.repo1.repoid
        assert reverse_response.data["results"][1]["repoid"] == self.repo2.repoid

    def test_get_active_repos(self, _):
        RepositoryFactory(author=self.org, name='C')
        response = self._get_repos({'active': True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            2,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )

    def test_get_inactive_repos(self, _):
        RepositoryFactory(author=self.org, name='C')
        response = self._get_repos({'active': False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            1,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )

    def test_get_all_repos(self, mock_provider):
        RepositoryFactory(author=self.org, name='C')
        response = self._get_repos({})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.data['results']),
            3,
            "got the wrong number of repos: {}".format(len(response.data['results']))
        )


@patch("internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class TestRepoView(InternalAPITest):
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

    def test_update_default_branch(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.patch('/internal/codecov/repo1/default-branch', data=json.dumps({'branch': 'dev'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(content['branch'], 'dev', "got unexpected response: {}".format(content['branch']))

    def test_update_default_branch_doesnt_update_other_field(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.patch('/internal/codecov/repo1/default-branch', data=json.dumps({'private': False}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        content = self.json_content(response)
        self.assertEqual(content['private'], True, "got unexpected response: {}".format(content['private']))

    def test_update_default_branch_not_allowed(self, mock_provider):
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.patch('/internal/codecov/repo1/default-branch', data=json.dumps({'branch': 'dev'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        content = self.json_content(response)
        assert 'branch' not in content


class TestRepoDetailsView(object):

    @override_settings(DEBUG=True)
    def test_repo_details_with_latest_commit_files(self, mocker, db, client, codecov_vcr):
        mock_repo_accessor = mocker.patch.object(RepoAccessors, 'get_repo_permissions')
        mock_repo_accessor.return_value = True, True
        user = OwnerFactory(username='codecov', service='github')
        client.force_login(user=user)
        repo = RepositoryFactory(author=user, active=True, private=True, name='repo1')
        commit = CommitFactory.create(
            message='test_commits_base',
            commitid='9193232a8fe3429496956ba82b5fed2583d1b5eb',
            repository=repo,
        )
        expected_report_result = build_mocked_report_archive(mocker)

        response = client.get('/internal/codecov/repo1/details')
        content = json.loads(response.content.decode())
        print(content)
        assert content['can_edit']
        assert content['latest_commit']
        assert content['latest_commit']['commitid'] == commit.commitid
        assert content['latest_commit']['report']['totals'] == expected_report_result['totals']
