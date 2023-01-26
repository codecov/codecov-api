from inspect import Parameter

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
)
from core.models import Commit
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
        components = commit_components(comparison.head_commit, request.user)
        component_comparisons = [
            ComponentComparison(comparison, component) for component in components
        ]

        serializer = ComponentComparisonSerializer(component_comparisons, many=True)
        return Response(serializer.data)
