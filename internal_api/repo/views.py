import uuid
import asyncio
import logging

from torngit.exceptions import TorngitClientError

from django.db.models import Subquery, OuterRef

from django.db.models import Subquery, OuterRef
from django.shortcuts import get_object_or_404

from rest_framework import generics, filters, mixins, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS # ['GET', 'HEAD', 'OPTIONS']
from rest_framework import status

from django_filters import rest_framework as django_filters, BooleanFilter

from internal_api.mixins import FilterByRepoMixin, RepoSlugUrlMixin
from codecov_auth.models import Owner
from core.models import Repository, Commit

from .repository_accessors import RepoAccessors
from .serializers import RepoSerializer, RepoDetailsSerializer, SecretStringPayloadSerializer

from .utils import encode_secret_string

from repo_providers.services import RepoProviderService

from .repository_actions import delete_webhook_on_provider, create_webhook_on_provider


class RepositoryFilters(django_filters.FilterSet):
    """Filter for active repositories"""
    active = BooleanFilter(field_name='active', method='filter_active')

    def filter_active(self, queryset, name, value):
        # The database currently stores 't' instead of 'true' for active repos, and nothing for inactive
        # so if the query param active is set, we return repos with non-null value in active column
        return queryset.filter(active__isnull=(not value))

    class Meta:
        model = Repository
        fields = ['active']


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

    def _get_owner(self):
        return get_object_or_404(
            Owner,
            username=self.kwargs.get("orgName"),
            service=self.request.user.service
        )

    def _assert_is_admin(self):
        owner = self._get_owner()
        if self.request.user.ownerid not in owner.admins:
            raise PermissionDenied()

    def get_serializer_class(self):
        if self.action == 'list':
            return RepoSerializer
        return RepoDetailsSerializer

    def get_serializer_context(self, *args, **kwargs):
        context = super().get_serializer_context(*args, **kwargs)
        if self.action != 'list':
            context.update({"can_edit": self.can_edit, "can_view": self.can_view})
        return context

    def get_queryset(self):
        owner = self._get_owner()
        queryset = owner.repository_set.all()

        if self.action == 'list':
            # Hiding this annotation will avoid expensive subqueries
            # used only for filtering list action on coverage metrics
            queryset = queryset.annotate(
                coverage=Subquery(
                    Commit.objects.filter(
                        repository_id=OuterRef('repoid')
                    ).order_by('-timestamp').values('totals__c')[:1]
                )
            )

        return queryset

    def check_object_permissions(self, request, repo):
        self.can_view, self.can_edit = self.accessors.get_repo_permissions(self.request.user, repo)
        if self.request.method not in SAFE_METHODS and not self.can_edit:
            raise PermissionDenied()
        if self.request.method == 'DELETE':
            self._assert_is_admin()
        if not self.can_view:
            raise PermissionDenied()

    def get_object(self):
        repo_name, org_name = self.kwargs.get('repoName'), self.kwargs.get('orgName')
        repo = self.accessors.get_repo_details(self.request.user, repo_name, org_name)
        self.check_object_permissions(self.request, repo)
        return repo

    def perform_update(self, serializer):
        # Check repo limits for users with legacy plans
        owner = self._get_owner()
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

        owner, repo = self._get_owner(), self.get_object()

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
    def reset_webhook(self, request, *args, **kwargs):
        repo = self.get_object()
        repository_service = RepoProviderService().get_adapter(self.request.user, repo)

        if repo.hookid:
            delete_webhook_on_provider(repository_service, repo)

        try:
            repo.hookid = create_webhook_on_provider(repository_service, repo)
            repo.save()
        except TorngitClientError:
            return Response(
                data={"message": f"Authorization declined by {repo.author.service} to create a webhook"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        return Response(
            self.get_serializer(repo).data,
            status=status.HTTP_200_OK
        )
