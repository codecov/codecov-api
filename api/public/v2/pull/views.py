from django.db.models import OuterRef, Subquery
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins

from api.public.v2.schema import repo_parameters
from api.shared.pull.mixins import PullViewSetMixin
from core.models import Pull

from .serializers import PullSerializer


@extend_schema(parameters=repo_parameters, tags=["Pulls"])
class PullViewSet(
    PullViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = PullSerializer
    queryset = Pull.objects.none()

    def get_queryset(self):
        return super().get_queryset().select_related("author")

    @extend_schema(summary="Pull list")
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of pulls for the specified repository

        Optionally filterable by:
        * the `state` of the pull

        Orderable by:
        * `pullid`
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Pull detail",
        parameters=[
            OpenApiParameter(
                "pullid",
                OpenApiTypes.STR,
                OpenApiParameter.PATH,
                description="pull ID",
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single pull by ID
        """
        return super().retrieve(request, *args, **kwargs)
