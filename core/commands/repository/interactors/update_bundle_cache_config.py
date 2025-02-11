from typing import Dict, List

from shared.django_apps.bundle_analysis.models import CacheConfig
from shared.django_apps.bundle_analysis.service.bundle_analysis import (
    BundleAnalysisCacheConfigService,
)

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from core.models import Repository


class UpdateBundleCacheConfigInteractor(BaseInteractor):
    def validate(
        self, repo: Repository, cache_config: List[Dict[str, str | bool]]
    ) -> None:
        # Find any missing bundle names
        bundle_names = [
            bundle["bundle_name"]
            for bundle in cache_config
            # the value of bundle_name is always a string, just do this check to appease mypy
            if isinstance(bundle["bundle_name"], str)
        ]
        existing_bundle_names = set(
            CacheConfig.objects.filter(
                repo_id=repo.pk, bundle_name__in=bundle_names
            ).values_list("bundle_name", flat=True)
        )
        missing_bundles = set(bundle_names) - existing_bundle_names
        if missing_bundles:
            raise ValidationError(
                f"The following bundle names do not exist: {', '.join(missing_bundles)}"
            )

    @sync_to_async
    def execute(
        self,
        owner_username: str,
        repo_name: str,
        cache_config: List[Dict[str, str | bool]],
    ) -> List[Dict[str, str | bool]]:
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, only_viewable=True
        )

        self.validate(repo, cache_config)

        results = []
        for bundle in cache_config:
            bundle_name = bundle["bundle_name"]
            is_caching = bundle["toggle_caching"]
            BundleAnalysisCacheConfigService.update_cache_option(
                repo.pk, bundle_name, is_caching
            )
            results.append(
                {
                    "bundle_name": bundle_name,
                    "is_cached": is_caching,
                    "cache_config": is_caching,
                }
            )
        return results
