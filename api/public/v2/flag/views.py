from rest_framework import mixins, viewsets

from api.public.v2.flag.serializers import FlagSerializer
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions


class FlagViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, RepoPropertyMixin):
    serializer_class = FlagSerializer
    permission_classes = [RepositoryArtifactPermissions]
    lookup_field = "flag_name"

    def get_queryset(self):
        return self.repo.flags.all()
