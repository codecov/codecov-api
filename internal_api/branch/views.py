from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from internal_api.mixins import FilterByRepoMixin
from core.models import Branch
from .serializers import BranchSerializer


class RepoBranchList(FilterByRepoMixin, generics.ListAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ('updatestamp', 'name')

    def filter_queryset(self, queryset):
        queryset = super(RepoBranchList, self).filter_queryset(queryset)
        author = self.request.GET.get('author')

        if author:
            return queryset.filter(authors__contains=[author])

        return queryset
