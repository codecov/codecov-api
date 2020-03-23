from django.test import TestCase

from unittest.mock import patch

from codecov_auth.models import (
    SERVICE_GITHUB,
    SERVICE_GITHUB_ENTERPRISE,
    SERVICE_BITBUCKET,
    SERVICE_BITBUCKET_SERVER,
    SERVICE_CODECOV_ENTERPRISE,
    DEFAULT_AVATAR_SIZE
)

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


class TestOwnerModel(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            username="codecov_name",
            service_id="1234",
            email="name@codecov.io",
            ownerid="4",
        )

    def test_repo_credits_returns_correct_repos_for_legacy_plan(self):
        self.owner.plan = '5m'
        assert self.owner.repo_credits == 5

    def test_repo_credits_returns_correct_repos_for_v4_plan(self):
        self.owner.plan = 'v4-100m'
        assert self.owner.repo_credits == 100

    def test_repo_credits_accounts_for_currently_active_private_repos(self):
        self.owner.plan = '5m'
        RepositoryFactory(author=self.owner, active=True, private=True)

        assert self.owner.repo_credits == 4

    def test_repo_credits_ignores_active_public_repos(self):
        self.owner.plan = '5m'
        RepositoryFactory(author=self.owner, active=True, private=True)
        RepositoryFactory(author=self.owner, active=True, private=False)

        assert self.owner.repo_credits == 4


    def test_repo_credits_returns_infinity_for_user_plans(self):
        users_plans = ('users', 'users-inappm', 'users-inappy', 'users-free')
        for plan in users_plans:
            self.owner.plan = plan
            assert self.owner.repo_credits == float('inf')

    def test_repo_credits_treats_null_plan_as_free_plan(self):
        assert self.owner.plan == None
        assert self.owner.repo_credits == 1 + self.owner.free or 0

    @patch("codecov_auth.models.get_config")
    def test_main_avatar_url_services(self, mock_get_config):
        test_cases=[
           {'service': SERVICE_GITHUB, 'get_config': None, 'expected': f'https://avatars0.githubusercontent.com/u/1234?v=3&s={DEFAULT_AVATAR_SIZE}'},
           {'service': SERVICE_GITHUB_ENTERPRISE, 'get_config': 'github_enterprise', 'expected': f'github_enterprise/avatars/u/1234?v=3&s={DEFAULT_AVATAR_SIZE}'},
           {'service': SERVICE_BITBUCKET, 'get_config': None, 'expected': f'https://bitbucket.org/account/codecov_name/avatar/{DEFAULT_AVATAR_SIZE}'},
        ]
        for i in range(0, len(test_cases)):
            with self.subTest(i=i):
                mock_get_config.return_value = test_cases[i]['get_config']
                self.owner.service = test_cases[i]['service']
                self.assertEqual(self.owner.avatar_url, test_cases[i]['expected'])

    @patch("codecov_auth.models.get_config")
    def test_bitbucket_without_u_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == SERVICE_BITBUCKET_SERVER and
                args[1] == 'url'):
                return SERVICE_BITBUCKET_SERVER

        mock_get_config.side_effect = side_effect
        self.owner.service = SERVICE_BITBUCKET_SERVER
        self.assertEqual(self.owner.avatar_url, f'bitbucket_server/projects/codecov_name/avatar.png?s={DEFAULT_AVATAR_SIZE}')

    @patch("codecov_auth.models.get_config")
    def test_bitbucket_with_u_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == SERVICE_BITBUCKET_SERVER and
                args[1] == 'url'):
                return SERVICE_BITBUCKET_SERVER

        mock_get_config.side_effect = side_effect
        self.owner.service = SERVICE_BITBUCKET_SERVER
        self.owner.service_id = 'U1234'
        self.assertEqual(self.owner.avatar_url, f'bitbucket_server/users/codecov_name/avatar.png?s={DEFAULT_AVATAR_SIZE}')

    @patch("codecov_auth.models.get_gitlab_url")
    def test_gitlab_service(self, mock_gitlab_url):
        mock_gitlab_url.return_value = 'gitlab_url'
        self.owner.service = 'gitlab'
        self.assertEqual(self.owner.avatar_url, 'gitlab_url')
        self.assertTrue(mock_gitlab_url.called_once())

    @patch("codecov_auth.models.get_config")
    def test_gravatar_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == 'services' and
                args[1] == 'gravatar'):
                return 'gravatar'

        mock_get_config.side_effect = side_effect
        self.owner.service = None
        self.assertEqual(self.owner.avatar_url, f'https://www.gravatar.com/avatar/9a74a018e6162103a2845e22ec5d88ef?s={DEFAULT_AVATAR_SIZE}')

    @patch("codecov_auth.models.get_config")
    def test_avatario_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == 'services' and
                args[1] == 'avatars.io'):
                return 'avatars.io'

        mock_get_config.side_effect = side_effect
        self.owner.service = None
        self.assertEqual(self.owner.avatar_url, f'https://avatars.io/avatar/9a74a018e6162103a2845e22ec5d88ef/{DEFAULT_AVATAR_SIZE}')

    @patch("codecov_auth.models.get_config")
    def test_ownerid_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == 'setup' and
                args[1] == 'codecov_url'):
                return 'codecov_url'
        mock_get_config.side_effect = side_effect
        self.owner.service = None
        self.assertEqual(self.owner.avatar_url, f'codecov_url/users/4.png?size={DEFAULT_AVATAR_SIZE}')

    @patch("codecov_auth.models.get_config")
    @patch("codecov_auth.models.os.getenv")
    def test_service_codecov_enterprise_url(self, mock_getenv, mock_get_config):
        def side_effect(*args):
            if (len(args) == 2 and args[0] == 'setup' and
                args[1] == 'codecov_url'):
                return 'codecov_url'
        mock_get_config.side_effect = side_effect
        mock_getenv.return_value = SERVICE_CODECOV_ENTERPRISE
        self.owner.service = None
        self.owner.ownerid = None
        self.assertEqual(self.owner.avatar_url, 'codecov_url/media/images/gafsi/avatar.svg')

    @patch("codecov_auth.models.get_config")
    def test_service_codecov_media_url(self, mock_get_config):
        def side_effect(*args):
            if (len(args) == 3 and args[0] == 'setup' and
                args[1] == 'media' and args[2] == 'assets'):
                return 'codecov_url_media'
        mock_get_config.side_effect = side_effect
        self.owner.service = None
        self.owner.ownerid = None
        self.assertEqual(self.owner.avatar_url, 'codecov_url_media/media/images/gafsi/avatar.svg')
