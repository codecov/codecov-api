import mmh3
from shared.django_apps.rollouts.models import (
    FeatureFlag,
    FeatureFlagVariant,
    RolloutUniverse,
)
from shared.django_apps.utils.model_utils import rollout_identifier_to_override_string
from shared.rollouts import Feature

FEATURES_CACHE_REDIS_KEY = "features_endpoint_cache"


def get_flag_cache_redis_key(flag_name):
    return FEATURES_CACHE_REDIS_KEY + ":" + flag_name


def get_identifier(feature_flag: FeatureFlag, identifier_data):
    """
    Returns the appropriate identifier string based on the rollout identifier type.
    """
    if feature_flag.rollout_identifier == RolloutUniverse.OWNER_ID:
        return identifier_data["user_id"]
    elif feature_flag.rollout_identifier == RolloutUniverse.REPO_ID:
        return identifier_data["repo_id"]
    elif feature_flag.rollout_identifier == RolloutUniverse.EMAIL:
        return identifier_data["email"]
    elif feature_flag.rollout_identifier == RolloutUniverse.ORG_ID:
        return identifier_data["org_id"]
    else:
        raise ValueError("Unknown RolloutUniverse type")
