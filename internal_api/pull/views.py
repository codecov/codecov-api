import asyncio

from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import Http404, get_object_or_404
from rest_framework import viewsets, mixins

from internal_api.mixins import FilterByRepoMixin, RepoSlugUrlMixin
from internal_api.compare.serializers import FlagComparisonSerializer
from services.comparison import get_comparison_from_pull_request
from core.models import Pull
from .serializers import PullSerializer, PullDetailSerializer


class RepoPullViewset(
    FilterByRepoMixin,
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin
):
    queryset = Pull.objects.all()
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter)
    filter_fields = ('state',)
    ordering_fields = ('updatestamp', 'head__timestamp')
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PullDetailSerializer
        elif self.action == 'list':
            return PullSerializer

    def get_object(self):
        queryset = super(RepoPullViewset, self).filter_queryset(self.queryset)
        pullid = self.kwargs['pk']
        obj = get_object_or_404(queryset, pullid=pullid)
        return obj

    def filter_queryset(self, queryset):
        queryset = super(RepoPullViewset, self).filter_queryset(queryset)
        return queryset

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

        try:
            return get_comparison_from_pull_request(obj, user)
        except Commit.DoesNotExist:
            raise Http404("Pull base or head references nonexistant commit.")

    def get_queryset(self):
        comparison = self.get_comparison()
        return list(
            comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags
        )
