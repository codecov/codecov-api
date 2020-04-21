import asyncio

from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import ValidationError

from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist

from codecov_auth.models import Owner
from core.models import Repository, Commit, Branch
from internal_api.repo.repository_accessors import RepoAccessors

from .serializers import CommitRefQueryParamSerializer, PullIDQueryParamSerializer


class RepoSlugUrlMixin:

    def get_repo(self):
        return get_object_or_404(
            Repository,
            name=self.kwargs.get("repoName"),
            author__username=self.kwargs.get("orgName"),
            author__service=self.request.user.service
        )


class CompareSlugMixin(RepoSlugUrlMixin):
    def _get_query_param_serializer_class(self):
        if "pullid" in self.request.query_params:
            return PullIDQueryParamSerializer
        return CommitRefQueryParamSerializer

    def get_commits(self):
        serializer = self._get_query_param_serializer_class()(
            data=self.request.query_params,
            context={"repo": self.get_repo()}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return validated_data["base"], validated_data["head"]


class FilterByRepoMixin(RepoSlugUrlMixin):
    """ Repository filter for commits/branches/pulls that uses the args:
        orgName, repoName, and permissions of the authenticated user """

    def filter_queryset(self, queryset, lookup_field = 'repository'):
        queryset = super().filter_queryset(queryset)
        repo = self.get_repo()
        return queryset.filter(**{ lookup_field: repo })
