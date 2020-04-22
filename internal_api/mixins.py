import asyncio

from rest_framework.exceptions import PermissionDenied
from rest_framework.serializers import ValidationError

from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist
from django.utils.functional import cached_property

from codecov_auth.models import Owner
from core.models import Repository, Commit, Branch
from internal_api.repo.repository_accessors import RepoAccessors

from .serializers import CommitRefQueryParamSerializer, PullIDQueryParamSerializer


class RepoPropertyMixin:

    @cached_property
    def repo(self):
        return get_object_or_404(
            Repository,
            name=self.kwargs.get("repoName"),
            author__username=self.kwargs.get("orgName"),
            author__service=self.request.user.service
        )


class CompareSlugMixin(RepoPropertyMixin):
    def _get_query_param_serializer_class(self):
        if "pullid" in self.request.query_params:
            return PullIDQueryParamSerializer
        return CommitRefQueryParamSerializer

    def get_commits(self):
        serializer = self._get_query_param_serializer_class()(
            data=self.request.query_params,
            context={"repo": self.repo}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return validated_data["base"], validated_data["head"]
