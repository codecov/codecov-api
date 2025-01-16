import hmac
import logging
from hashlib import sha256

from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import GithubAppInstallation, Owner
from graphql_api.types.owner.owner import AI_FEATURES_GH_APP_ID
from utils.config import get_config

log = logging.getLogger(__name__)


class GenAIAuthView(APIView):
    permission_classes = [AllowAny]

    def validate_signature(self, request):
        key = get_config(
            "gen_ai", "auth_secret", default=b"testixik8qdauiab1yiffydimvi72ekq"
        )
        if isinstance(key, str):
            key = key.encode("utf-8")
        expected_sig = request.META.get("HTTP_X_GEN_AI_AUTH_SIGNATURE")
        computed_sig = (
            "sha256=" + hmac.new(key, request.body, digestmod=sha256).hexdigest()
        )
        if not (expected_sig and constant_time_compare(computed_sig, expected_sig)):
            raise PermissionDenied("Invalid signature")

    def post(self, request, *args, **kwargs):
        self.validate_signature(request)
        external_owner_id = request.data.get("external_owner_id")
        repo_service_id = request.data.get("repo_service_id")
        if not external_owner_id or not repo_service_id:
            return Response("Missing required parameters", status=400)
        try:
            owner = Owner.objects.get(service_id=external_owner_id)
        except Owner.DoesNotExist:
            raise NotFound("Owner not found")

        is_authorized = True

        app_install = GithubAppInstallation.objects.filter(
            owner_id=owner.ownerid, app_id=AI_FEATURES_GH_APP_ID
        ).first()

        if not app_install:
            print("FAILED")
            is_authorized = False

        else:
            repo_ids = app_install.repository_service_ids
            if repo_ids and repo_service_id not in repo_ids:
                print("HERE")
                is_authorized = False

        return Response({"is_valid": is_authorized})


# api/gen_ai/tests/test_gen_ai.py
