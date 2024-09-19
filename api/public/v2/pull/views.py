import django_filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from api.public.v2.schema import repo_parameters
from api.shared.pagination import PaginationMixin
from api.shared.permissions import RepositoryArtifactPermissions, SuperTokenPermissions
from api.shared.pull.mixins import PullViewSetMixin
from codecov_auth.authentication import (
    SuperTokenAuthentication,
    UserTokenAuthentication,
)
from core.models import Pull, PullStates

from .serializers import PullSerializer


class PullFilters(django_filters.FilterSet):
    state = django_filters.ChoiceFilter(choices=PullStates.choices)
    start_date = django_filters.DateTimeFilter(method="filter_start_date")

    def filter_start_date(self, queryset, name, value):
        return queryset.filter(updatestamp__gte=value)


@extend_schema(parameters=repo_parameters, tags=["Pulls"])
class PullViewSet(
    PaginationMixin,
    PullViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    authentication_classes = [
        SuperTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]

    permission_classes = [SuperTokenPermissions | RepositoryArtifactPermissions]

    serializer_class = PullSerializer
    queryset = Pull.objects.none()
    filterset_class = PullFilters

    def get_queryset(self):
        return super().get_queryset().select_related("author")

    @extend_schema(
        summary="Pull list",
        parameters=[
            OpenApiParameter(
                "state",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                description="the state of the pull (open/merged/closed)",
            ),
            OpenApiParameter(
                "start_date",
                OpenApiTypes.DATETIME,
                OpenApiParameter.QUERY,
                description="only return pulls with updatestamp on or after this date",
            ),
        ],
    )
    def list(self, request, *args, **kwargs):
        """
        Returns a paginated list of pulls for the specified repository

        Optionally filterable by:
        * `state`
        * `start_date`

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
