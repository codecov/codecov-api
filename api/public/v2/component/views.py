from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import viewsets
from rest_framework.response import Response

from api.public.v2.component.serializers import ComponentSerializer
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from services.components import commit_components


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
    def list(self, request, *args, **kwargs):
        """
        Returns a list of components for the specified repository
        """
        commit = self.get_commit()
        components = commit_components(commit, request.user)
        serializer = ComponentSerializer(components, many=True)
        return Response(serializer.data)
