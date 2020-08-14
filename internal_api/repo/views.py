import uuid
import logging

from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS # ['GET', 'HEAD', 'OPTIONS']
from rest_framework import status

from django_filters import rest_framework as django_filters, BooleanFilter
from internal_api.repo.filter import StringListFilter

from core.models import Repository
from services.repo_providers import RepoProviderService
from services.decorators import torngit_safe
from internal_api.permissions import RepositoryPermissionsService
from internal_api.mixins import OwnerPropertyMixin

from .repository_accessors import RepoAccessors
from .serializers import (
    RepoWithMetricsSerializer,
    RepoDetailsSerializer,
    SecretStringPayloadSerializer,
)

from .utils import encode_secret_string

from .repository_actions import delete_webhook_on_provider, create_webhook_on_provider


log = logging.getLogger(__name__)


class RepositoryFilters(django_filters.FilterSet):
    """Filter for active repositories"""
    active = BooleanFilter(field_name='active', method='filter_active')

    """Filter for getting multiple repositories by name"""
    names = StringListFilter(query_param='names', field_name='name', lookup_expr='in')

    def filter_active(self, queryset, name, value):
        # The database currently stores 't' instead of 'true' for active repos, and nothing for inactive
        # so if the query param active is set, we return repos with non-null value in active column
        return queryset.filter(active__isnull=(not value))

    class Meta:
        model = Repository
        fields = ['active', 'names']


class RepositoryViewSet(
        mixins.ListModelMixin,
        mixins.RetrieveModelMixin,
        mixins.UpdateModelMixin,
        mixins.DestroyModelMixin,
        viewsets.GenericViewSet,
        OwnerPropertyMixin
    ):

    filter_backends = (django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = RepositoryFilters
    search_fields = ('name',)
    ordering_fields = ('updatestamp', 'name', 'coverage',)
    lookup_value_regex = '[\w\.@\:\-~]+'
    lookup_field = 'repo_name'
    accessors = RepoAccessors()

    def _assert_is_admin(self):
        if not self.owner.is_admin(self.request.user):
            raise PermissionDenied()

    def get_serializer_class(self):
        if self.action == 'list':
            return RepoWithMetricsSerializer
        return RepoDetailsSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        if self.action != 'list':
            context.update({"can_edit": self.can_edit, "can_view": self.can_view})
        return context

    def get_queryset(self):
        queryset = self.owner.repository_set.viewable_repos(
            self.request.user
        ).select_related(
            "author"
        )

        if self.action == 'list':
            if self.request.query_params.get("exclude_uncovered", False):
                queryset = queryset.exclude_uncovered()

            queryset = queryset.with_current_coverage(
            ).with_latest_coverage_change(
            ).with_total_commit_count()

        return queryset

    @torngit_safe
    def check_object_permissions(self, request, repo):
        self.can_view, self.can_edit = self.accessors.get_repo_permissions(self.request.user, repo)

        if repo.private and not RepositoryPermissionsService().user_is_activated(self.request.user, self.owner):
            raise PermissionDenied("User not activated")
        if self.request.method not in SAFE_METHODS and not self.can_edit:
            raise PermissionDenied()
        if self.request.method == 'DELETE':
            self._assert_is_admin()
        if not self.can_view:
            raise PermissionDenied()

    @torngit_safe
    def get_object(self):
        # Get request args and try to find the repo in the DB
        repo_name = self.kwargs.get('repo_name')
        org_name = self.kwargs.get('owner_username')
        service = self.kwargs.get('service')

        repo = self.accessors.get_repo_details(
            user=self.request.user,
            repo_name=repo_name,
            repo_owner_username=org_name,
            repo_owner_service=service
        )

        if repo is None:
            repo = self.accessors.fetch_from_git_and_create_repo(
                user=self.request.user,
                repo_name=repo_name,
                repo_owner_username=org_name,
                repo_owner_service=service
            )

        self.check_object_permissions(self.request, repo)
        return repo

    def perform_update(self, serializer):
        # Check repo limits for users with legacy plans
        owner = self.owner
        if serializer.validated_data.get('active'):
            if owner.has_legacy_plan and owner.repo_credits <= 0:
                raise PermissionDenied("Private repository limit reached.")
        return super().perform_update(serializer)

    @action(detail=True, methods=['patch'], url_path='regenerate-upload-token')
    def regenerate_upload_token(self, request, *args, **kwargs):
        repo = self.get_object()
        repo.upload_token = uuid.uuid4()
        repo.save()
        return Response(self.get_serializer(repo).data)

    @action(detail=True, methods=['patch'])
    def erase(self, request, *args, **kwargs):
        self._assert_is_admin()
        repo = self.get_object()
        repo.flush()
        return Response(self.get_serializer(repo).data)

    @action(detail=True, methods=['post'])
    def encode(self, request, *args, **kwargs):
        serializer = SecretStringPayloadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        owner, repo = self.owner, self.get_object()

        to_encode = '/'.join((
            owner.service,
            owner.service_id,
            repo.service_id,
            serializer.validated_data['value']
        ))

        return Response(
            SecretStringPayloadSerializer(
                {"value": encode_secret_string(to_encode)}
            ).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['put'], url_path='reset-webhook')
    @torngit_safe
    def reset_webhook(self, request, *args, **kwargs):
        repo = self.get_object()
        repository_service = RepoProviderService().get_adapter(self.request.user, repo)

        if repo.hookid:
            delete_webhook_on_provider(repository_service, repo)
            repo.hookid = None
            repo.save()

        repo.hookid = create_webhook_on_provider(repository_service, repo)
        repo.save()

        return Response(
            self.get_serializer(repo).data,
            status=status.HTTP_200_OK
        )
