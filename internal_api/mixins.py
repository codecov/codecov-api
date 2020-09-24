from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from codecov_auth.models import Owner
from core.models import Repository

from .serializers import CommitRefQueryParamSerializer, PullIDQueryParamSerializer

short_services = {
    'gh': 'github',
    'bb': 'bitbucket',
    'gl': 'gitlab'
}

class OwnerPropertyMixin:
    @cached_property
    def owner(self):
        service = short_services[self.kwargs.get("service")] if self.kwargs.get("service") in short_services else self.kwargs.get("service")
        return get_object_or_404(
            Owner,
            username=self.kwargs.get("owner_username"),
            service=service
        )


class RepoPropertyMixin(OwnerPropertyMixin):
    @cached_property
    def repo(self):
        return get_object_or_404(
            Repository,
            name=self.kwargs.get("repo_name"),
            author=self.owner
        )


class RepositoriesMixin:
    @cached_property
    def repositories(self):
        """
        List of repositories passed in through request query parameters. Used when generating chart response data.
        """
        return Repository.objects.filter(
            name__in=self.request.data.get("repositories", []),
            author__username=self.kwargs.get("owner_username"),
        )


class CompareSlugMixin(RepoPropertyMixin):
    def _get_query_param_serializer_class(self):
        if "pullid" in self.request.query_params:
            return PullIDQueryParamSerializer
        return CommitRefQueryParamSerializer

    def get_commits(self):
        serializer = self._get_query_param_serializer_class()(
            data=self.request.query_params, context={"repo": self.repo}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return validated_data["base"], validated_data["head"]
