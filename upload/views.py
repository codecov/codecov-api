import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import ValidationError
from django.http import HttpResponse
from urllib.parse import parse_qs

from .helpers import (
    parse_params,
    get_global_tokens,
    determine_repo_and_owner_for_upload,
    determine_upload_branch_to_use,
    determine_upload_pr_to_use,
    determine_upload_commitid_to_use,
    insert_commit,
)

log = logging.getLogger(__name__)


class UploadHandler(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        response["Accept"] = "text/*"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Method"] = "POST"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        return response

    def post(self, request, *args, **kwargs):
        # Extract the version
        version = self.kwargs["version"]

        log.info(
            "Received upload request",
            extra=dict(version=version, query_params=self.request.query_params),
        )

        # Set response headers
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        if version == "v4":
            response["Content-Type"] = "text/plain"
            request.META["HTTP_ACCEPT"] = "text/plain"

        # Parse request parameters
        request_params = {
            **self.request.query_params.dict(),  # query_params is a QueryDict, need to convert to dict to process it properly
            **self.kwargs,
        }
        try:
            upload_params = parse_params(request_params)
        except ValidationError as e:
            log.error(
                "Failed to parse upload request params",
                extra=dict(request_params=request_params, errors=str(e)),
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Invalid request parameters"
            return response

        # Try to determine the repository associated with the upload based on the params provided
        try:
            repository, owner = determine_repo_and_owner_for_upload(upload_params)
        except ValidationError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Could not determine repo and owner"
            return response

        # TODO other stuff

        # Save commit
        branch = determine_upload_branch_to_use(upload_params, repository.branch)
        pr = determine_upload_pr_to_use(upload_params)
        commitid = determine_upload_commitid_to_use(upload_params)

        insert_commit(
            commitid, branch, pr, repository, owner, upload_params.get("parent")
        )

        # Update repo and set it to active if it's not already
        if repository.active == False or repository.deleted == True:
            repository.active = True
            repository.deleted = False
            repository.save()

        return response
