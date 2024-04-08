from loguru import logger
from json import dumps

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from sentry_sdk import metrics as sentry_metrics
from shared.validation.exceptions import InvalidYamlException
from shared.yaml.validation import validate_yaml
from yaml import YAMLError, safe_load


class V1ValidateYamlHandler(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return HttpResponse(
            f"Usage:\n\ncurl -X POST --data-binary @codecov.yml {settings.CODECOV_URL}/validate\n",
            status=status.HTTP_200_OK,
            content_type="text/plain",
        )

    def post(self, request, *args, **kwargs):
        if not self.request.body:
            return HttpResponse(
                "No content posted.",
                status=status.HTTP_400_BAD_REQUEST,
                content_type="text/plain",
            )

        # Parse the yaml from the request body
        try:
            yaml_dict = safe_load(self.request.body)

            if not isinstance(yaml_dict, dict):
                logger.warning(
                    f"yaml_dict result from loading validate request body is not a dict",
                    extra=dict(
                        yaml_dict=yaml_dict, request_body=str(self.request.body)
                    ),
                )
                return HttpResponse(
                    "No file posted.",
                    status=status.HTTP_400_BAD_REQUEST,
                    content_type="text/plain",
                )

        except YAMLError as e:
            return HttpResponse(
                "Can't parse YAML\n",
                status=status.HTTP_400_BAD_REQUEST,
                content_type="text/plain",
            )

        # Validate the parsed yaml
        try:
            validated_yaml = validate_yaml(yaml_dict)
            return HttpResponse(
                f"Valid!\n\n{dumps(validated_yaml, indent=2)}\n",
                status=status.HTTP_200_OK,
                content_type="text/plain",
            )

        except InvalidYamlException as e:
            return HttpResponse(
                f"Error at {str(e.error_location)}: \n{e.error_message}\n",
                status=status.HTTP_400_BAD_REQUEST,
                content_type="text/plain",
            )


class V2ValidateYamlHandler(V1ValidateYamlHandler):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        source = self.request.query_params.get("source", "unknown")
        sentry_metrics.incr("validate_v2", tags={"source": source})

        if not self.request.body:
            return Response(
                {
                    "valid": False,
                    "message": "YAML is empty",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse the yaml from the request body
        try:
            yaml_dict = safe_load(self.request.body)
            if not isinstance(yaml_dict, dict):
                logger.warning(
                    f"yaml_dict result from loading validate request body is not a dict",
                    extra=dict(
                        yaml_dict=yaml_dict, request_body=str(self.request.body)
                    ),
                )
                return Response(
                    {
                        "valid": False,
                        "message": "YAML must be a dictionary type",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except YAMLError as e:
            mark = e.problem_mark
            return Response(
                {
                    "valid": False,
                    "message": "YAML could not be parsed",
                    "parse_error": {
                        "problem": e.problem,
                        "line": mark.line + 1,
                        "column": mark.column + 1,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate the parsed yaml
        try:
            validated_yaml = validate_yaml(yaml_dict)
            return Response(
                {
                    "valid": True,
                    "message": "YAML is valid",
                    "validated_yaml": validated_yaml,
                }
            )

        except InvalidYamlException as e:
            return Response(
                {
                    "valid": False,
                    "message": "YAML does not match the accepted schema",
                    "validation_error": e.error_dict,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
