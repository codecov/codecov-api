import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions, SuperTokenPermissions
from codecov_auth.authentication import (
    SuperTokenAuthentication,
    UserTokenAuthentication,
)
from reports.models import TestInstance

from .serializers import TestInstanceSerializer


class TestResultsFilters(django_filters.FilterSet):
    commit_id = django_filters.CharFilter(field_name="commitid")
    outcome = django_filters.CharFilter(field_name="outcome")
    duration_min = django_filters.NumberFilter(
        field_name="duration_seconds", lookup_expr="gte"
    )
    duration_max = django_filters.NumberFilter(
        field_name="duration_seconds", lookup_expr="lte"
    )
    branch = django_filters.CharFilter(field_name="branch")

    class Meta:
        model = TestInstance
        fields = ["commit_id", "outcome", "duration_min", "duration_max", "branch"]


@extend_schema(
    parameters=[
        OpenApiParameter(
            "commit_id",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="Commit SHA for which to return test results",
        ),
        OpenApiParameter(
            "outcome",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="Status of the test (failure, skip, error, pass)",
        ),
        OpenApiParameter(
            "duration_min",
            OpenApiTypes.INT,
            OpenApiParameter.QUERY,
            description="Minimum duration of the test in seconds",
        ),
        OpenApiParameter(
            "duration_max",
            OpenApiTypes.INT,
            OpenApiParameter.QUERY,
            description="Maximum duration of the test in seconds",
        ),
        OpenApiParameter(
            "branch",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="Branch name for which to return test results",
        ),
    ],
    tags=["Test Results"],
    summary="Retrieve test results",
)
class TestResultsView(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    RepoPropertyMixin,
):
    authentication_classes = [
        SuperTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]

    serializer_class = TestInstanceSerializer
    permission_classes = [SuperTokenPermissions | RepositoryArtifactPermissions]
    filter_backends = [DjangoFilterBackend]
    filterset_class = TestResultsFilters

    def get_queryset(self):
        return TestInstance.objects.filter(repoid=self.repo.repoid)

    @extend_schema(summary="Test results list")
    def list(self, request, *args, **kwargs):
        """
        Returns a list of test results for the specified repository and commit
        """
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Test results detail",
        parameters=[
            OpenApiParameter(
                "id",
                OpenApiTypes.INT,
                OpenApiParameter.PATH,
                description="Test instance ID",
            ),
        ],
    )
    def retrieve(self, request, *args, **kwargs):
        """
        Returns a single test result by ID
        """
        return super().retrieve(request, *args, **kwargs)
