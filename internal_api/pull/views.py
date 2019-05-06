from rest_framework import generics, filters
from internal_api.mixins import RepoFilterMixin
from .models import Pull
from .serializers import PullSerializer


class RepoPullsView(RepoFilterMixin, generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer
    filter_backends = (filters.OrderingFilter,)
    ordering = '-updatestamp'