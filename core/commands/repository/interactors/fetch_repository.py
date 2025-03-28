import sentry_sdk
from asgiref.sync import sync_to_async
from shared.django_apps.codecov_auth.models import Owner
from shared.django_apps.core.models import Repository

from codecov.commands.base import BaseInteractor


class FetchRepositoryInteractor(BaseInteractor):
    @sync_to_async
    @sentry_sdk.trace
    def execute(
        self,
        owner: Owner,
        name: str,
        okta_authenticated_accounts: list[int],
        exclude_okta_enforced_repos: bool = True,
    ) -> Repository | None:
        queryset = Repository.objects.viewable_repos(self.current_owner)
        if exclude_okta_enforced_repos:
            queryset = queryset.exclude_accounts_enforced_okta(
                okta_authenticated_accounts
            )

        # TODO(swatinem): We should find a way to avoid these combinators:
        # The `with_recent_coverage` combinator is quite expensive.
        # We only need that in case we want to query these props via graphql:
        # `coverageAnalytics.{percentCovered,commitSha,hits,misses,lines}`
        # Similarly, `with_oldest_commit_at` is only needed for `oldestCommitAt`.

        repo = (
            queryset.filter(author=owner, name=name)
            .with_recent_coverage()
            .with_oldest_commit_at()
            .select_related("author")
            .first()
        )

        return repo
