from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.authentication import SlackTokenAuthentication
from codecov_auth.models import Owner, UserToken

from .helpers import validate_params


class GenerateAccessTokenView(APIView):
    """
    Returns a new access token for the given user for slack integration
    """

    authentication_classes = [SlackTokenAuthentication]
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.headers.get("username")
        service = request.headers.get("service")
        validate_params(username, service)

        owner = Owner.objects.get(username=username, service=service)
        if not owner:
            return Response({"error": "Owner not found"}, status=404)

        token_type = UserToken.TokenType.API.value
        user_token = UserToken.objects.create(
            name="slack-codecov-access-token",
            owner=owner,
            token_type=token_type,
        )
        user_token.save()
        return Response({"token": user_token.token}, status=200)
