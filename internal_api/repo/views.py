import uuid
import asyncio
import logging

from shared.torngit.exceptions import TorngitClientError

from django.db.models import Subquery, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property

from rest_framework import generics, filters, mixins, viewsets
from rest_framework.exceptions import PermissionDenied, APIException, NotFound
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS # ['GET', 'HEAD', 'OPTIONS']
from rest_framework import status

from django_filters import rest_framework as django_filters, BooleanFilter, BaseInFilter

from codecov_auth.models import Owner
from core.models import Repository, Commit
from services.repo_providers import RepoProviderService
from services.decorators import torngit_safe

from .repository_accessors import RepoAccessors
from .serializers import RepoWithTotalSerializer, RepoDetailsSerializer, SecretStringPayloadSerializer

from .utils import encode_secret_string

from .repository_actions import delete_webhook_on_provider, create_webhook_on_provider


log = logging.getLogger(__name__)


class RepositoryFilters(django_filters.FilterSet):
    """Filter for active repositories"""
    active = BooleanFilter(field_name='active', method='filter_active')

    """Filter for getting multiple repositories by name"""
    names = BaseInFilter(field_name='name', lookup_expr='in')

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
        viewsets.GenericViewSet
    ):

    filter_backends = (django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = RepositoryFilters
    search_fields = ('name',)
    ordering_fields = ('updatestamp', 'name', 'coverage',)
    lookup_value_regex = '[\w\.@\:\-~]+'
    lookup_field = 'repoName'
    accessors = RepoAccessors()

    @cached_property
    def owner(self):
        # Usable everywhere except for in .get_object(), becauses the owner
        # may not exist yet.
        return get_object_or_404(
            Owner,
            username=self.kwargs.get("orgName"),
            service=self.kwargs.get("service")
        )

    def _assert_is_admin(self):
        owner = self.owner
        if self.request.user.ownerid != owner.ownerid:
            if owner.admins is None or self.request.user.ownerid not in owner.admins:
                raise PermissionDenied()

    def get_serializer_class(self):
        if self.action == 'list':
            return RepoWithTotalSerializer
        return RepoDetailsSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        if self.action != 'list':
            context.update({"can_edit": self.can_edit, "can_view": self.can_view})
        return context

    def get_queryset(self):
        queryset = self.owner.repository_set.filter(
            Q(private=False)
            | Q(author__ownerid=self.request.user.ownerid)
            | Q(repoid__in=self.request.user.permission)
        )

        if self.action == 'list':
            # Hiding this annotation will avoid expensive subqueries
            # used only for filtering list action on coverage metrics
            queryset = queryset.annotate(
                coverage=Subquery(
                    Commit.objects.filter(
                        repository_id=OuterRef('repoid')
                    ).order_by('-timestamp').values('totals__c')[:1]
                ),
                totals = Subquery(
                    Commit.objects.filter(
                        repository_id=OuterRef('repoid')
                    ).order_by('-timestamp').values('totals')[:1]
                )
            )

        return queryset

    @torngit_safe
    def check_object_permissions(self, request, repo):
        self.can_view, self.can_edit = self.accessors.get_repo_permissions(self.request.user, repo)
        if self.request.method not in SAFE_METHODS and not self.can_edit:
            raise PermissionDenied()
        if self.request.method == 'DELETE':
            self._assert_is_admin()
        if not self.can_view:
            raise PermissionDenied()

    @torngit_safe
    def get_object(self):
        # Get request args and try to find the repo in the DB
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
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
