from rest_framework import generics
from rest_framework import filters
from django_filters import rest_framework as django_filters, BooleanFilter
from codecov_auth.models import Owner
from core.models import Repository
from .serializers import RepoSerializer


class RepositoryFilter(django_filters.FilterSet):
    """Filter for active repositories"""
    active = BooleanFilter(field_name='active', method='filter_active')

    def filter_active(self, queryset, name, value):
        # The database currently stores 't' instead of 'true' for active repos, and nothing for inactive
        # so if the query param active is set, we return repos with non-null value in active column
        return queryset.filter(active__isnull=False)

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
        organization = Owner.objects.get(username=org_name, service=self.request.user.service)
        queryset = queryset.filter(author=organization, repoid__in=owner.permission)
        return queryset
