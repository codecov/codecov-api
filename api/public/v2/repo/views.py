from django_filters import rest_framework as django_filters
from rest_framework import filters, mixins, viewsets

from api.shared.repo.filter import RepositoryFilters
from api.shared.repo.mixins import RepositoryViewSetMixin

from .serializers import RepoSerializer


class RepositoryViewSet(
    RepositoryViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):

    filter_backends = (
        django_filters.DjangoFilterBackend,
        filters.SearchFilter,
    )
    filterset_class = RepositoryFilters
    search_fields = ("name",)
    ordering_fields = (
        "updatestamp",
        "name",
    )
    serializer_class = RepoSerializer
