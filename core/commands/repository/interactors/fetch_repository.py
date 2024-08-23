from shared.django_apps.codecov_auth.models import Owner
from shared.django_apps.core.models import Repository

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async


class FetchRepositoryInteractor(BaseInteractor):
    @sync_to_async
    def execute(
        self,
        owner: Owner,
        name: str,
        okta_authenticated_accounts: list[int],
        exclude_okta_enforced_repos: bool = True,
    ):
        queryset = Repository.objects.viewable_repos(self.current_owner)
        if exclude_okta_enforced_repos:
            queryset = queryset.exclude_accounts_enforced_okta(
                okta_authenticated_accounts
            )

        return (
            queryset.filter(author=owner, name=name)
            .with_recent_coverage()
            .with_oldest_commit_at()
            .select_related("author")
            .first()
        )
