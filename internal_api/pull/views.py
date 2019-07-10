import asyncio

from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import Http404

from internal_api.mixins import RepoFilterMixin, RepoSlugUrlMixin
from internal_api.compare.serializers import FlagComparisonSerializer
from compare.services import get_comparison_from_pull_request
from core.models import Pull
from .serializers import PullSerializer


class RepoPullList(RepoFilterMixin, generics.ListAPIView):
    queryset = Pull.objects.all()
    serializer_class = PullSerializer
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filter_fields = ('state',)
    ordering_fields = ('updatestamp', 'head__timestamp')


class RepoPullFlagsList(RepoSlugUrlMixin, generics.ListCreateAPIView):
    serializer_class = FlagComparisonSerializer

    def get_comparison(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        user = self.request.user
        repo = self.get_repo()
        pullid = self.kwargs['pullid']
        pull_requests = Pull.objects.filter(
            repository=repo,
            pullid=pullid
        )
        try:
            obj = pull_requests.get()
        except Pull.DoesNotExist:
            raise Http404('No pull matches the given query.')
        return get_comparison_from_pull_request(obj, user)

    def get_queryset(self):
        comparison = self.get_comparison()
        return list(
            comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags
        )
