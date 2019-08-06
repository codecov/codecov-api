import asyncio

from rest_framework import generics
from rest_framework import filters
from django_filters import rest_framework as django_filters, BooleanFilter
from rest_framework.exceptions import PermissionDenied

from codecov_auth.models import Owner
from core.models import Repository, Commit
from internal_api.repo.repository_accessors import RepoAccessors
from .serializers import RepoSerializer, RepoDetailsSerializer, RepoNewUploadTokenSerializer


class RepositoryFilter(django_filters.FilterSet):
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
    queryset = Repository.objects.all()
    serializer_class = RepoSerializer
    filter_backends = (django_filters.DjangoFilterBackend, filters.SearchFilter)
    filterset_class = RepositoryFilter
    search_fields = ('name',)

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        org_name = self.kwargs.get('orgName')
        owner = self.request.user
        organization = Owner.objects.get(username=org_name, service=owner.service)
        queryset = queryset.filter(author=organization)
        return queryset


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