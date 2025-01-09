import logging
import pickle
from typing import Any, Dict, List

from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.django_apps.rollouts.models import FeatureFlag
from shared.rollouts import Feature

from api.internal.feature.helpers import get_flag_cache_redis_key, get_identifier
from services.redis_configuration import get_redis_connection
from utils.config import get_config

from .serializers import FeatureRequestSerializer

log = logging.getLogger(__name__)


class FeaturesView(APIView):
    skip_feature_cache = get_config("setup", "skip_feature_cache", default=False)
    timeout = 300

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.redis = get_redis_connection()
        super().__init__(*args, **kwargs)

    def get_many_from_redis(self, keys: List) -> Dict[str, Any]:
        ret = self.redis.mget(keys)
        return {k: pickle.loads(v) for k, v in zip(keys, ret) if v is not None}

    def set_many_to_redis(self, data: Dict[str, Any]) -> None:
        pipeline = self.redis.pipeline()
        pipeline.mset({k: pickle.dumps(v) for k, v in data.items()})

        # Setting timeout for each key as redis does not support timeout
        # with mset().
        for key in data:
            pipeline.expire(key, self.timeout)
        pipeline.execute()

    def post(self, request: Request) -> Response:
        serializer = FeatureRequestSerializer(data=request.data)
        if serializer.is_valid():
            flag_evaluations = {}
            identifier_data = serializer.validated_data["identifier_data"]
            feature_flag_names = serializer.validated_data["feature_flags"]

            feature_flag_cache_keys = [
                get_flag_cache_redis_key(flag_name) for flag_name in feature_flag_names
            ]
            cache_misses = []

            if not self.skip_feature_cache:
                # fetch flags from cache
                cached_flags = self.get_many_from_redis(feature_flag_cache_keys)

                for ind in range(len(feature_flag_cache_keys)):
                    cache_key = feature_flag_cache_keys[ind]
                    flag_name = feature_flag_names[ind]

                    # if flag is in cache, make the evaluation. Otherwise, we'll
                    # fetch the flag from DB later
                    if cache_key in cached_flags:
                        feature_flag = cached_flags[cache_key]
                        identifier = get_identifier(feature_flag, identifier_data)

                        flag_evaluations[flag_name] = Feature(
                            flag_name, feature_flag, list(feature_flag.variants.all())
                        ).check_value_no_fetch(identifier=identifier)
                    else:
                        cache_misses.append(flag_name)
            else:
                cache_misses = feature_flag_names
                log.warning(
                    "skip_feature_cache for Feature should only be turned on in development environments, and should not be used in production"
                )

            flags_to_add_to_cache = {}

            # fetch flags not in cache
            missed_feature_flags = FeatureFlag.objects.filter(
                name__in=cache_misses
            ).prefetch_related("variants")  # include the feature flag variants aswell

            # evaluate the remaining flags
            for feature_flag in missed_feature_flags:
                identifier = get_identifier(feature_flag, identifier_data)

                flag_evaluations[feature_flag.name] = Feature(
                    feature_flag.name, feature_flag, list(feature_flag.variants.all())
                ).check_value_no_fetch(identifier=identifier)
                flags_to_add_to_cache[get_flag_cache_redis_key(feature_flag.name)] = (
                    feature_flag
                )

            # add the new flags to cache
            if len(flags_to_add_to_cache) >= 1:
                self.set_many_to_redis(flags_to_add_to_cache)

            return Response(flag_evaluations, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
