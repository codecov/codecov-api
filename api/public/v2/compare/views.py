from distutils.util import strtobool
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from api.public.v2.schema import repo_parameters
from api.shared.compare.mixins import CompareViewSetMixin
from api.shared.compare.serializers import (
    FileComparisonSerializer,
    FlagComparisonSerializer,
    ImpactedFilesComparisonSerializer,
    ImpactedFileSegmentsSerializer,
)
from services.components import ComponentComparison, commit_components
from services.decorators import torngit_safe

from .serializers import ComparisonSerializer, ComponentComparisonSerializer

comparison_parameters = [
    OpenApiParameter(
        "pullid",
        OpenApiTypes.INT,
        OpenApiParameter.QUERY,
        description="pull ID on which to perform the comparison (alternative to specifying `base` and `head`)",
    ),
    OpenApiParameter(
        "base",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        description="base commit SHA (`head` also required)",
    ),
    OpenApiParameter(
        "head",
        OpenApiTypes.STR,
        OpenApiParameter.QUERY,
        description="head commit SHA (`base` also required)",
    ),
]


@extend_schema(parameters=repo_parameters, tags=["Comparison"])
class CompareViewSet(
    CompareViewSetMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = ComparisonSerializer

    def get_queryset(self):
        return None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "has_diff" in self.request.query_params:
            context.update(
                {"has_diff": strtobool(self.request.query_params["has_diff"])}
            )
        return context

    @extend_schema(
        summary="Comparison",
        parameters=comparison_parameters,
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a comparison for either a pair of commits or a pull
        """
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="File comparison",
        parameters=comparison_parameters
        + [
            OpenApiParameter(
                "file_path",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="file path",
            ),
        ],
        responses={200: FileComparisonSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="file/(?P<file_path>.+)",
        url_name="file",
    )
    def file(self, request, *args, **kwargs):
        """
        Returns a comparison for a specific file path
        """
        return super().file(request, *args, **kwargs)

    @extend_schema(
        summary="Flag comparison",
        parameters=comparison_parameters,
        responses={200: FlagComparisonSerializer},
    )
    @action(detail=False, methods=["get"])
    def flags(self, request, *args, **kwargs):
        """
        Returns flag comparisons
        """
        return super().flags(request, *args, **kwargs)

    @extend_schema(
        summary="Component comparison",
        parameters=comparison_parameters,
        responses={200: ComponentComparisonSerializer},
    )
    @action(detail=False, methods=["get"])
    @torngit_safe
    def components(self, request, *args, **kwargs):
        """
        Returns component comparisons
        """
        comparison = self.get_object()
        components = commit_components(comparison.head_commit, self.owner)
        component_comparisons = [
            ComponentComparison(comparison, component) for component in components
        ]

        serializer = ComponentComparisonSerializer(component_comparisons, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Impacted files comparison",
        parameters=comparison_parameters,
        responses={200: ImpactedFilesComparisonSerializer},
    )
    @action(detail=False, methods=["get"])
    def impacted_files(self, request, *args, **kwargs):
        """
        Returns a comparison for either a pair of commits or a pull
        Will only return pre-computed impacted files comparisons if available
        If unavailable `files` will be empty, however once the computation is ready
        the files will appear on subsequent calls
        `state: "processed"` means `files` are finished computing and returned
        `state: "pending"` means `files` are still computing, poll again later
        """
        return super().impacted_files(request, *args, **kwargs)

    @extend_schema(
        summary="Segmented file comparison",
        parameters=comparison_parameters
        + [
            OpenApiParameter(
                "file_path",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="file path",
            ),
        ],
        responses={200: ImpactedFileSegmentsSerializer},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="segments/(?P<file_path>.+)",
        url_name="segments",
    )
    def segments(self, request, *args, **kwargs):
        """
        Returns a comparison for a specific file path only showing the segments
        of the file that are impacted instead of all lines in file
        """
        return super().segments(request, *args, **kwargs)
