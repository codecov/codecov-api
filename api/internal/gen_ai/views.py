from graphql_api.types.owner.owner import AI_FEATURES_GH_APP_ID
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.license import get_current_license

from .serializers import GenAIAuthSerializer, LicenseSerializer

from codecov_auth.models import (
    GithubAppInstallation,
    Owner,
)

class GenAIAuthView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        owner_id = request.query_params.get("owner_id")
        owner = Owner.objects.filter(pk=owner_id, service="github").first()

        ai_features_app_install = None
        repos = []

        if owner:
            ai_features_app_install = GithubAppInstallation.objects.filter(
                app_id=AI_FEATURES_GH_APP_ID, owner=owner
            ).first()

        if ai_features_app_install and ai_features_app_install.repository_service_ids:
                repos = ai_features_app_install.repository_service_ids

        data = {
            "is_valid": bool(ai_features_app_install),
            "repos": repos,
        }

        serializer = GenAIAuthSerializer(data)
        return Response(serializer.data)
