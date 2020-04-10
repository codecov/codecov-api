import asyncio

from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied

from services.comparison import Comparison
from services.repo_providers import RepoProviderService

from internal_api.compare.serializers import (
    FileComparisonSerializer,
    ComparisonSerializer,
    FlagComparisonSerializer,
)

from internal_api.mixins import CompareSlugMixin
from internal_api.repo.repository_accessors import RepoAccessors


class CompareViewSet(CompareSlugMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ComparisonSerializer

    def check_object_permissions(self, _):
        repo = self.get_repo()
        can_view, _ = RepoAccessors().get_repo_permissions(self.request.user, repo)
        if not can_view:
            raise PermissionDenied()

    def get_object(self):
        base, head = self.get_commits()
        comparison = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        self.check_object_permissions(comparison)
        asyncio.set_event_loop(asyncio.new_event_loop())
        return comparison

    @action(detail=False, methods=['get'], url_path='file/(?P<file_path>.+)')
    def file(self, request, *args, **kwargs):
        comparison = self.get_object()
        file_path = file_path=kwargs.get('file_path')
        if file_path not in comparison.head_report:
            raise NotFound("File not found in head report.")
        return Response(
            FileComparisonSerializer(
                comparison.get_file_comparison(file_path, with_src=True, bypass_max_diff=True)
            ).data
        )

    @action(detail=False, methods=['get'])
    def flags(self, request, *args, **kwargs):
        comparison = self.get_object()
        flags = [comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags]
        return Response(FlagComparisonSerializer(flags, many=True).data)
