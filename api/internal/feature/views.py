from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.django_apps.rollouts.models import FeatureFlag

from api.internal.feature.helpers import evaluate_flag, get_flag_cache_redis_key

from .serializers import FeatureRequestSerializer


class FeaturesView(APIView):
    def post(self, request):
        serializer = FeatureRequestSerializer(data=request.data)
        if serializer.is_valid():
            flag_evaluations = {}
            identifier_data = serializer.validated_data["identifier_data"]

            feature_flag_names = serializer.validated_data["feature_flags"]
            feature_flag_cache_keys = [
                get_flag_cache_redis_key(flag_name) for flag_name in feature_flag_names
            ]
            cache_misses = []

            # fetch flags from cache
            cached_flags = cache.get_many(feature_flag_cache_keys)

            for ind in range(len(feature_flag_cache_keys)):
                cache_key = feature_flag_cache_keys[ind]
                flag_name = feature_flag_names[ind]

                # if flag is in cache, make the evaluation. Otherwise, we'll
                # fetch the flag from DB later
                if cache_key in cached_flags:
                    hits += 1
                    flag_evaluations[flag_name] = evaluate_flag(
                        cached_flags[cache_key], identifier_data
                    )
                else:
                    cache_misses.append(flag_name)
                    misses += 1

            flags_to_add_to_cache = {}

            # fetch flags not in cache
            missed_feature_flags = FeatureFlag.objects.filter(
                name__in=cache_misses
            ).prefetch_related(
                "variants"
            )  # include the feature flag variants aswell

            # evaluate the remaining flags
            for feature_flag in missed_feature_flags:
                flag_evaluations[feature_flag.name] = evaluate_flag(
                    feature_flag, identifier_data
                )
                flags_to_add_to_cache[
                    get_flag_cache_redis_key(feature_flag.name)
                ] = feature_flag

            # add the new flags to cache
            if len(flags_to_add_to_cache) >= 1:
                cache.set_many(flags_to_add_to_cache)

            return Response(flag_evaluations, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
