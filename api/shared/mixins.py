from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from api.shared.serializers import (
    CommitRefQueryParamSerializer,
    PullIDQueryParamSerializer,
)
from codecov_auth.authentication import SuperToken, SuperUser
from codecov_auth.models import Owner, Service
from core.models import Repository
from utils.services import get_long_service_name


class OwnerPropertyMixin:
    @cached_property
    def owner(self):
        service = get_long_service_name(self.kwargs.get("service"))
        if service not in Service:
            raise Http404("Invalid service for Owner.")

        return get_object_or_404(
            Owner, username=self.kwargs.get("owner_username"), service=service
        )


class RepoPropertyMixin(OwnerPropertyMixin):
    @cached_property
    def repo(self):
        return get_object_or_404(
            Repository, name=self.kwargs.get("repo_name"), author=self.owner
        )


class RepositoriesMixin:
    @cached_property
    def repositories(self):
        """
        List of repositories passed in through request query parameters. Used when generating chart response data.
        """
        service = get_long_service_name(self.kwargs.get("service"))

        return Repository.objects.filter(
            name__in=self.request.data.get("repositories", []),
            author__username=self.kwargs.get("owner_username"),
            author__service=service,
        )


class CompareSlugMixin(RepoPropertyMixin):
    def _get_query_param_serializer_class(self):
        if "pullid" in self.request.query_params:
            return PullIDQueryParamSerializer
        return CommitRefQueryParamSerializer

    def get_compare_data(self):
        serializer = self._get_query_param_serializer_class()(
            data=self.request.query_params, context={"repo": self.repo}
        )
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        return validated_data


class SuperPermissionsMixin:
    def has_super_token_permissions(self, request):
        if request.method != "GET":
            return False
        user = request.user
        auth = request.auth

        if not isinstance(request.user, SuperUser) or not isinstance(
            request.auth, SuperToken
        ):
            return False
        return (
            user.is_super_user
            and auth.is_super_token
            and auth.token == settings.SUPER_API_TOKEN
        )
