from rest_framework import status
from rest_framework.response import Response
from json import dumps

from covreports.validation import validate_yaml, InvalidYamlException


class ValidateYamlHandler(APIView):
    def post(self):
        if not self.request.body:
            return Response(status=status.HTTP_400_BAD_REQUEST, data='No content posted.')
        else:
            try:
                validated_yml = self.validate_yaml(self.request.body)
                return Response(status=status.HTTP_200_OK, data=f"Valid!\n\n{dumps(validated_yml, indent=2)}\n")
            except InvalidYamlException:
                self.log('error', 'User encoutered error while validating yaml file', remote_ip=str(self.request.remote_ip), request_body=self.request.body)
                return Response(status=status.HTTP_400_BAD_REQUEST)