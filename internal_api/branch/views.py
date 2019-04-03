from rest_framework import generics
from internal_api.views import RepoFilter
from .models import Branch
from .serializers import BranchSerializer


class RepoBranchesView(RepoFilter, generics.ListCreateAPIView):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer