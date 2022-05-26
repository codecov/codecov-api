from rest_framework.response import Response
from rest_framework.views import APIView
from shared.config import _get_config_instance
from shared.license import get_current_license, load_raw_license_into_dict

from .serializers import LicenseSerializer


class LicenseView(APIView):
    def get(self, request, format=None):
        license = get_current_license()
        serializer = LicenseSerializer(license)

        return Response(serializer.data)
