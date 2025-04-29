from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission

EMPTY_RESPONSE = {
    "external_id": None,
    "state": "finished",
    "errors": [],
    "requested_labels": [],
    "base_commit": "",
    "head_commit": "",
    "result": {
        "absent_labels": [],
        "present_diff_labels": [],
        "present_report_labels": [],
        "global_level_labels": [],
    },
}


class LabelAnalysisRequestView(APIView):
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    # TODO Consider using a different permission scope
    required_scopes = ["static_analysis"]

    def post(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE, status=status.HTTP_201_CREATED)

    def get(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE)

    def patch(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE)
