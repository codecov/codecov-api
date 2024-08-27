from typing import Any

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response

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

    def get_queryset(self) -> QuerySet:
        results = [
            {"flag_name": f.flag_name, "coverage": None} for f in self.repo.flags.all()
        ]
        try:
            report = self.get_commit().full_report
            if not report:
                return results
        except NotFound:
            return results

        for i, val in enumerate(results):
            flag_report = report.filter(flags=[val["flag_name"]])
            results[i]["coverage"] = flag_report.totals.coverage or 0
        return results

    @extend_schema(summary="Flag list")
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns a paginated list of flags for the specified repository
        """
        return super().list(request, *args, **kwargs)
