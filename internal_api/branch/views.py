from rest_framework import generics
from internal_api.mixins import RepoFilterMixin
from .models import Branch
from .serializers import BranchSerializer


class RepoBranchesView(RepoFilterMixin, generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer