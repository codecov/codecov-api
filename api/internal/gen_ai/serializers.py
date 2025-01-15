from graphql_api.types.owner.owner import AI_FEATURES_GH_APP_ID
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from codecov_auth.models import GithubAppInstallation, Owner
from shared.django_apps.core.models import Repository
from shared.license import get_current_license


class GenAIAuthSerializer(serializers.Serializer):
    is_valid = serializers.BooleanField()
    repos = serializers.ListField(child=serializers.CharField(), required=False)

