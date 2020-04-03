from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from yaml import safe_load, YAMLError
from django.http import HttpResponse
from json import dumps
from django.conf import settings

from covreports.validation.yaml import validate_yaml
from covreports.validation.exceptions import InvalidYamlException


class ValidateYamlHandler(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return HttpResponse(f"Usage:\n\ncurl -X POST --data-binary @codecov.yml {settings.CODECOV_URL}/validate\n", status=status.HTTP_200_OK, content_type="text/plain")

    def post(self, request, *args, **kwargs):
        if not self.request.body:
            return HttpResponse("No content posted.", status=status.HTTP_400_BAD_REQUEST, content_type="text/plain")

        try:
            yaml_dict = safe_load(self.request.body)
        except YAMLError as e:
            return HttpResponse(f"{str(e)}\n", status=status.HTTP_400_BAD_REQUEST, content_type="text/plain")
        try:
            validated_yaml = validate_yaml(yaml_dict)
            return HttpResponse(f"Valid!", status=status.HTTP_200_OK, content_type="text/plain")
            # TODO: return validated yaml as done below after addressing
            # https://codecovio.atlassian.net/browse/CE-1484
            # return HttpResponse(f"Valid!\n\n{dumps(validated_yaml, indent=2)}\n", status=status.HTTP_200_OK, content_type="text/plain")
        except InvalidYamlException as e:
            return HttpResponse(f"{str(e)}\n", status=status.HTTP_400_BAD_REQUEST, content_type="text/plain")
