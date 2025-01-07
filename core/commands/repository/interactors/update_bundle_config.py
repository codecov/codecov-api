from typing import Dict, List

from shared.django_apps.bundle_analysis.models import CacheConfig

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.models import Repository


class UploadBundleConfigInteractor(BaseInteractor):
    def validate(
        self, repo: Repository, cache_config: List[Dict[str, str | bool]]
    ) -> None:
        if not repo:
            raise ValidationError("Repo not found")

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
        author = Owner.objects.filter(
            username=owner_username, service=self.service
        ).first()
        repo = (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=author, name=repo_name)
            .first()
        )

        self.validate(repo, cache_config)

        results = []
        for bundle in cache_config:
            bundle_name = bundle["bundle_name"]
            is_caching = bundle["toggle_caching"]
            CacheConfig.objects.filter(repo_id=repo.pk, bundle_name=bundle_name).update(
                is_caching=is_caching
            )
            results.append(
                {
                    "bundle_name": bundle_name,
                    "is_cached": is_caching,
                }
            )
        return results
