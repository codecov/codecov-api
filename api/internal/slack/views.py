from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.shared.permissions import InternalTokenPermissions
from codecov_auth.authentication import InternalTokenAuthentication
from codecov_auth.models import Owner, UserToken

from .helpers import validate_params


class GenerateAccessTokenView(APIView):
    """
    Returns a new access token for the given user for slack integration
    """

    authentication_classes = [InternalTokenAuthentication]
    permission_classes = [InternalTokenPermissions]

    def post(self, request, *args, **kwargs):
        username = request.headers.get("username")
        service = request.headers.get("service")
        validate_params(username, service)

        owner = Owner.objects.filter(username=username, service=service).first()
        if not owner:
            raise NotFound("Owner not found")

        token_type = UserToken.TokenType.API.value
        user_token, _ = UserToken.objects.get_or_create(
            name="slack-codecov-access-token",
            owner=owner,
            token_type=token_type,
        )
        return Response({"token": user_token.token}, status=200)
