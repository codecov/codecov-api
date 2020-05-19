import asyncio
import minio

from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied

from services.comparison import Comparison
from services.repo_providers import RepoProviderService
from services.decorators import torngit_safe

from internal_api.compare.serializers import (
    FileComparisonSerializer,
    ComparisonSerializer,
    FlagComparisonSerializer,
)

from internal_api.mixins import CompareSlugMixin
from internal_api.repo.repository_accessors import RepoAccessors
from internal_api.permissions import RepositoryArtifactPermissions


class CompareViewSet(CompareSlugMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ComparisonSerializer
    permission_classes = [RepositoryArtifactPermissions]

    def get_object(self):
        base, head = self.get_commits()
        comparison = Comparison(base_commit=base, head_commit=head, user=self.request.user)
        asyncio.set_event_loop(asyncio.new_event_loop())
        return comparison

    @torngit_safe
    def retrieve(self, request, *args, **kwargs):
        # Fetching the head report in the comparison can throw a minio error
        # if the report has been evicted from storage, so we translaate that
        # error into an API exception here
        try:
            return super().retrieve(request, *args, **kwargs)
        except minio.error.NoSuchKey:
            raise NotFound("Raw report not found for base or head reference.")

    @action(detail=False, methods=['get'], url_path='file/(?P<file_path>.+)', url_name="file")
    @torngit_safe
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
