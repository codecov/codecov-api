from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from api.shared.permissions import InternalTokenPermissions
from codecov_auth.authentication import InternalTokenAuthentication
from codecov_auth.models import Owner, UserToken

class IntegrationsView(APIView):
    def get(self, request, service_id):
        exists = Owner.objects.filter(service_id=service_id).exists()
        return Response({'exists': exists})
