from django.test import TestCase
from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


class OwnerUnitTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory()

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

