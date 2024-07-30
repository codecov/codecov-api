from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner


class CheckOwnerView(APIView):
    def get(self, request, service_id):
        exists = Owner.objects.filter(service_id=service_id).exists()
        return Response({'exists': exists})
