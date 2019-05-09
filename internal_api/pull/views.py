from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from internal_api.mixins import RepoFilterMixin
from .models import Pull
from .serializers import PullSerializer


class RepoPullsView(generics.ListCreateAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filter_fields = ('state',)
    ordering_fields = ('updatestamp', 'head__timestamp')
