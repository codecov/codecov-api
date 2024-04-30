from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.django_apps.rollouts.models import FeatureFlag

from api.internal.feature.helpers import evaluate_flag

from .serializers import FeatureRequestSerializer


class FeaturesView(APIView):
    def post(self, request):
        serializer = FeatureRequestSerializer(data=request.data)
        if serializer.is_valid():

            feature_flag_names = serializer.validated_data["feature_flags"]
            identifier_data = serializer.validated_data["identifier_data"]

            feature_flags = FeatureFlag.objects.filter(
                name__in=feature_flag_names
            ).prefetch_related(
                "variants"
            )  # fetch the feature flag variants aswell

            result = {}
            for feature_flag in feature_flags:
                result[feature_flag.name] = evaluate_flag(feature_flag, identifier_data)

            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
