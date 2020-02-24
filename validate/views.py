from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from yaml import safe_load, YAMLError
from django.http import HttpResponse
from json import dumps

from covreports.validation.exceptions import InvalidYamlException
from covreports.validation.yaml import validate_yaml
from utils.config import get_config


class ValidateYamlHandler(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return HttpResponse(f"Usage:\n\ncurl -X POST --data-binary @codecov.yml {get_config('setup', 'codecov_url')}/validate\n", content_type="text/plain")

    def post(self, request, *args, **kwargs):
        if not self.request.body:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='No content posted.')
        else:
            try:
                yaml_dict = safe_load(self.request.body)
            except YAMLError as e:
                raise InvalidYamlException('invalid_yaml', e)
            try:
                validated_yml = validate_yaml(yaml_dict)
                return HttpResponse(f"Valid!\n\n{dumps(validated_yml, indent=2)}\n")
            except InvalidYamlException:
                self.log('error', 'User encoutered error while validating yaml file', remote_ip=str(self.request.remote_ip), request_body=self.request.body)
                return Response(status=status.HTTP_400_BAD_REQUEST)
