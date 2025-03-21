from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from codecov_auth.permissions import SpecificScopePermission

EMPTY_RESPONSE = {
    "external_id": "0000",
    "filepaths": [],
    "commit": "",
}


class StaticAnalysisSuiteView(APIView):
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [SpecificScopePermission]
    required_scopes = ["static_analysis"]

    def post(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE, status=status.HTTP_201_CREATED)
