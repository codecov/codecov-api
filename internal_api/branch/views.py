from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, BaseCSVFilter, CharFilter

from internal_api.mixins import RepoFilterMixin
from .models import Branch
from .serializers import BranchSerializer


# class CharArrayFilter(BaseCSVFilter, CharFilter):
#     pass


# class BranchFilter(FilterSet):
#     class Meta:
#         model = Branch
#         fields = {
#             'authors': ['contains']
#         }


class RepoBranchesView(generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    ordering_fields = ('updatestamp', 'name')
