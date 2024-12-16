from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from api.public.v2.component.serializers import ComponentSerializer
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from services.components import commit_components, component_filtered_report
from utils import round_decimals_down


@extend_schema(
    parameters=repo_parameters
    + [
        OpenApiParameter(
            "sha",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="commit SHA for which to return components",
        ),
        OpenApiParameter(
            "branch",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="branch name for which to return components (of head commit)",
        ),
    ],
    tags=["Components"],
)
class ComponentViewSet(viewsets.ViewSet, RepoPropertyMixin):
    serializer_class = ComponentSerializer
    permission_classes = [RepositoryArtifactPermissions]

    @extend_schema(summary="Component list")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns a list of components for the specified repository
        """
        commit = self.get_commit()
        report = commit.full_report
        components = commit_components(commit, self.owner)
        components_with_coverage = []
        for component in components:
            component_report = component_filtered_report(report, [component])
            coverage = None
            if component_report.totals.coverage is not None:
                coverage = round_decimals_down(
                    float(component_report.totals.coverage), 2
                )
            components_with_coverage.append(
                {
                    "component_id": component.component_id,
                    "name": component.name,
                    "coverage": coverage,
                }
            )

        serializer = ComponentSerializer(components_with_coverage, many=True)
        return Response(serializer.data)
