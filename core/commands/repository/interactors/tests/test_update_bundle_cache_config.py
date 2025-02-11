import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.bundle_analysis.models import CacheConfig
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    RepositoryFactory,
)

from codecov.commands.exceptions import ValidationError

from ..update_bundle_cache_config import UpdateBundleCacheConfigInteractor


class UpdateBundleCacheConfigInteractorTest(TransactionTestCase):
    databases = {"default"}

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(permission=[self.repo.pk])

    @async_to_sync
    def execute(self, owner, repo_name=None, cache_config=[]):
        return UpdateBundleCacheConfigInteractor(owner, "github").execute(
            repo_name=repo_name,
            owner_username="test-org",
            cache_config=cache_config,
        )

    def test_repo_not_found(self):
        with pytest.raises(ValidationError):
            self.execute(owner=self.user, repo_name="wrong")

    def test_bundle_not_found(self):
        with pytest.raises(
            ValidationError, match="The following bundle names do not exist: wrong"
        ):
            self.execute(
                owner=self.user,
                repo_name="test-repo",
                cache_config=[{"bundle_name": "wrong", "toggle_caching": True}],
            )

    def test_some_bundles_not_found(self):
        CacheConfig.objects.create(
            repo_id=self.repo.pk, bundle_name="bundle1", is_caching=True
        )
        with pytest.raises(
            ValidationError, match="The following bundle names do not exist: bundle2"
        ):
            self.execute(
                owner=self.user,
                repo_name="test-repo",
                cache_config=[
                    {"bundle_name": "bundle1", "toggle_caching": False},
                    {"bundle_name": "bundle2", "toggle_caching": True},
                ],
            )

    def test_update_bundles_successfully(self):
        CacheConfig.objects.create(
            repo_id=self.repo.pk, bundle_name="bundle1", is_caching=True
        )
        CacheConfig.objects.create(
            repo_id=self.repo.pk, bundle_name="bundle2", is_caching=True
        )

        res = self.execute(
            owner=self.user,
            repo_name="test-repo",
            cache_config=[
                {"bundle_name": "bundle1", "toggle_caching": False},
                {"bundle_name": "bundle2", "toggle_caching": True},
            ],
        )

        assert res == [
            {"bundle_name": "bundle1", "is_cached": False, "cache_config": False},
            {"bundle_name": "bundle2", "is_cached": True, "cache_config": True},
        ]

        assert len(CacheConfig.objects.all()) == 2

        query = CacheConfig.objects.filter(repo_id=self.repo.pk, bundle_name="bundle1")
        assert len(query) == 1
        assert query[0].is_caching == False

        query = CacheConfig.objects.filter(repo_id=self.repo.pk, bundle_name="bundle2")
        assert len(query) == 1
        assert query[0].is_caching == True
