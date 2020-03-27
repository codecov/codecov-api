import asyncio

from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound

from services.comparison import Comparison
from services.repo_providers import RepoProviderService

from internal_api.compare.serializers import (
    ComparisonSerializer,
    SingleFileDiffSerializer,
    SingleFileSourceSerializer,
    FlagComparisonSerializer,
)

from internal_api.mixins import CompareSlugMixin


class CompareViewSet(CompareSlugMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = ComparisonSerializer

    def get_object(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        base, head = self.get_commits()
        return Comparison(base_commit=base, head_commit=head, user=self.request.user)

    @action(detail=False, methods=['get'], url_path='diff_file/(?P<file_path>.+)')
    def diff_file(self, request, *args, **kwargs):
        comparison = self.get_object()
        diff_coverage = comparison.file_diff(file_path=kwargs.get('file_path'))
        if diff_coverage is None:
            raise NotFound(f"'{kwargs.get('file_path')} not found in diff!")
        return Response(
            data=SingleFileDiffSerializer(diff_coverage).data
        )

    @action(detail=False, methods=['get'], url_path='src_file/(?P<file_path>.+)')
    def src_file(self, request, *args, **kwargs):
        comparison = self.get_object()
        file_path = kwargs.get('file_path')
        before = request.query_params.get('before')

        head_report_file = comparison.head_report.get(file_path)
        if not head_report_file:
            raise NotFound("File was not found in head report")

        base_report_file = comparison.base_report.get(before) if before else comparison.base_report.get(file_path)
        if not base_report_file:
            raise NotFound("File was not found in base report")

        source = asyncio.run(RepoProviderService().get_adapter(
            owner=request.user,
            repo=comparison.head_commit.repository
        ).get_source(
            file_path, comparison.head_commit.commitid
        ))

        return Response(
            data=SingleFileSourceSerializer({
                "src": source["content"].splitlines()
            }).data
        )

    @action(detail=False, methods=['get'])
    def flags(self, request, *args, **kwargs):
        comparison = self.get_object()
        flags = [comparison.flag_comparison(flag_name) for flag_name in comparison.available_flags]
        return Response(FlagComparisonSerializer(flags, many=True).data)
