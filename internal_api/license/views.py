from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.license import get_current_license

from .serializers import LicenseSerializer


class LicenseView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        license = get_current_license()
        serializer = LicenseSerializer(license)

        return Response(serializer.data)
