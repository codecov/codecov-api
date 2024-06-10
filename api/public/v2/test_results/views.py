from rest_framework.response import Response
from rest_framework import status
from api.shared.permissions import RepositoryArtifactPermissions
from reports.models import TestInstance
from .serializers import TestInstanceSerializer
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from api.shared.mixins import RepoPropertyMixin
from rest_framework import viewsets

@extend_schema(
    parameters=[
        OpenApiParameter(
            "commit_id",
            OpenApiTypes.STR,
            OpenApiParameter.QUERY,
            description="Commit SHA for which to return test results",
        ),
        OpenApiParameter(
            "test_status",
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
class TestResultsView(viewsets.ViewSet, RepoPropertyMixin):
    serializer_class = TestInstanceSerializer
    permission_classes = [RepositoryArtifactPermissions]

    @extend_schema(summary="Test results list")
    def list(self, request, *args, **kwargs):
        """
        Returns a list of test results for the specified repository and commit
        """
        required_params = ["commit_id", "branch"]
        params = request.query_params
        if not any(param in params for param in required_params):
            return Response(
                {"error": "Missing required parameter commit_id or branch"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        filters = {}
        if "commit_id" in params:
            filters["commitid"] = params["commit_id"]
        if "test_status" in params:
            filters["outcome"] = params["test_status"]
        if "duration_min" in params:
            filters["duration_seconds__gte"] = params["duration_min"]
        if "duration_max" in params:
            filters["duration_seconds__lte"] = params["duration_max"]
        if "branch" in params:
            filters["branch"] = params["branch"]

        test_results = TestInstance.objects.filter(**filters)

        serializer = TestInstanceSerializer(test_results, many=True)
        return Response(serializer.data)
