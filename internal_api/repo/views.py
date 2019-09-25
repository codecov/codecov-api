from django.db.models import Subquery, OuterRef

from django.shortcuts import get_object_or_404

from rest_framework import generics, filters, mixins
from rest_framework.exceptions import PermissionDenied

from django_filters import rest_framework as django_filters, BooleanFilter

from internal_api.mixins import FilterByRepoMixin, RepoSlugUrlMixin
from codecov_auth.models import Owner
from core.models import Repository, Commit

from .repository_accessors import RepoAccessors
from .serializers import RepoSerializer, RepoDetailsSerializer, RepoNewUploadTokenSerializer


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


class RepositoryList(generics.ListAPIView):
    serializer_class = RepoSerializer
    filter_backends = (django_filters.DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = RepositoryFilters
    search_fields = ('name',)
    ordering_fields = ('updatestamp', 'name', 'coverage',)

    def get_queryset(self):
        owner = get_object_or_404(
            Owner,
            username=self.kwargs.get("orgName"),
            service=self.request.user.service
        )
        return owner.repository_set.annotate(
            coverage=Subquery(
                Commit.objects.filter(
                    repository_id=OuterRef('repoid')
                ).order_by('-timestamp').values('totals__c')[:1]
            )
        )


class RepositoryDetails(generics.RetrieveAPIView):
    queryset = Repository.objects.all()
    serializer_class = RepoDetailsSerializer

    def get_object(self):
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        repo = RepoAccessors().get_repo_details(self.request.user, repo_name, org_name)
        return repo

    def get_serializer_context(self):
        context = super().get_serializer_context()
        repo = self.get_object()
        can_view, can_edit = RepoAccessors().get_repo_permissions(self.request.user, repo.name, repo.author.username)
        if repo.private and not can_view:
            raise PermissionDenied(detail="You do not have permissions to view this repo")
        has_uploads = Commit.objects.filter(repository=repo).exists()
        context['can_view'] = can_view
        context['can_edit'] = can_edit
        context['has_uploads'] = has_uploads
        return context


class RepositoryRegenerateUploadToken(generics.RetrieveUpdateAPIView):
    serializer_class = RepoNewUploadTokenSerializer

    def get_object(self):
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        repo = RepoAccessors().get_repo_details(self.request.user, repo_name, org_name)
        can_view, can_edit = RepoAccessors().get_repo_permissions(self.request.user, repo.name, repo.author.username)
        if not can_edit:
            raise PermissionDenied(detail="You do not have permissions to edit this repo")
        return repo


class RepositoryDefaultBranch(generics.RetrieveUpdateAPIView):
    serializer_class = RepoSerializer

    def get_object(self):
        repo_name = self.kwargs.get('repoName')
        org_name = self.kwargs.get('orgName')
        repo = RepoAccessors().get_repo_details(self.request.user, repo_name, org_name)
        can_view, can_edit = RepoAccessors().get_repo_permissions(self.request.user, repo.name, repo.author.username)
        if not can_edit:
            raise PermissionDenied(detail="Do not have permissions to edit this repo")
        return repo
