from rest_framework import generics
from internal_api.views import OwnerFilter
from .models import Repository
from .serializers import RepoSerializer


class RepoView(OwnerFilter, generics.ListCreateAPIView):
    queryset = Repository.objects.filter(active=True)
    serializer_class = RepoSerializer