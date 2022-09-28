from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets

from api.public.v2.flag.serializers import FlagSerializer
from api.public.v2.schema import repo_parameters
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions
from reports.models import RepositoryFlag


@extend_schema(parameters=repo_parameters, tags=["Flags"])
class FlagViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, RepoPropertyMixin):
    serializer_class = FlagSerializer
    permission_classes = [RepositoryArtifactPermissions]
    lookup_field = "flag_name"
    queryset = RepositoryFlag.objects.none()

    def get_queryset(self):
        return self.repo.flags.all()

    @extend_schema(summary="Flag list")
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of flags for the specified repository
        """
        return super().list(request, *args, **kwargs)
