import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.http import HttpResponse

from .helpers import validate_params

log = logging.getLogger(__name__)


class UploadHandler(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def post(self, request, *args, **kwargs):
        log.info(
            "Received upload request",
            extra=dict(
                version=self.kwargs["version"], arguments=self.request.query_params
            ),
        )

        request_params = {**self.request.query_params, **self.kwargs}  # TODO validate
        version = request_params["version"]

        # Set response headers
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        if version == "v4":
            response["Content-Type"] = "text/plain"
            request.META["HTTP_ACCEPT"] = "text/plain"

        return response

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        response["Accept"] = "text/*"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Method"] = "POST"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        return response
