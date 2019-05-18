from rest_framework import generics

from internal_api.mixins import OwnerFilterMixin
from core.models import Repository
from .serializers import RepoSerializer


class RepoView(OwnerFilterMixin, generics.ListCreateAPIView):
    queryset = Repository.objects.filter(active=True)
    serializer_class = RepoSerializer
