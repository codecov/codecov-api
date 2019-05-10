from rest_framework import generics, filters
from django_filters import FilterSet, BaseCSVFilter, CharFilter
from django_filters.rest_framework import DjangoFilterBackend

from internal_api.mixins import RepoFilterMixin
from .models import Branch
from .serializers import BranchSerializer


class RepoBranchesView(generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ('updatestamp', 'name')

    def filter_queryset(self, queryset):
        queryset = super(RepoBranchesView, self).filter_queryset(queryset)
        author = self.request.GET.get('author')

        if author:
            return queryset.filter(authors__contains=[author])

        return queryset
