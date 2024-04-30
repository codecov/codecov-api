import mmh3
from shared.django_apps.rollouts.models import (
    FeatureFlag,
    FeatureFlagVariant,
    RolloutIdentifier,
)
from shared.django_apps.utils.model_utils import rollout_identifier_to_override_string
from shared.rollouts import Feature

# TODO: these function should ideally be consolidated with
# what the `Feature` util in `shared.rollouts/__init__.py` uses
# into some flag service module so that the core logic of flags
# is shared between the two interfaces of `/internal/features` endpoint
# and the `Feature` util.


def get_identifier(feature_flag: FeatureFlag, identifier_data):
    """
    Returns the appropriate identifier string based on the rollout identifier type.
    """
    if feature_flag.rollout_identifier == RolloutIdentifier.OWNER_ID:
        return identifier_data["user_id"]
    elif feature_flag.rollout_identifier == RolloutIdentifier.REPO_ID:
        return identifier_data["repo_id"]
    elif feature_flag.rollout_identifier == RolloutIdentifier.EMAIL:
        return identifier_data["email"]
    elif feature_flag.rollout_identifier == RolloutIdentifier.ORG_ID:
        return identifier_data["org_id"]
    else:
        raise ValueError("Unknown RolloutIdentifier type")


def get_override_variant(
    feature_flag: FeatureFlag, identifier, identifier_override_field
):
    """
    Retrieves the feature variant applicable to the given identifer according to
    the overrides
    """
    for variant in feature_flag.variants.all():
        if identifier in getattr(variant, identifier_override_field):
            return variant
    return None


def compute_buckets(feature_flag):
    """
    Computes the bucket boundaries for the feature variants
    """
    buckets = []
    quantile = 0

    for variant in feature_flag.variants.all():
        variant_test_population = int(variant.proportion * Feature.HASHSPACE)

        start = int(quantile * Feature.HASHSPACE)
        end = int(start + (variant_test_population * feature_flag.proportion))

        quantile += variant.proportion
        buckets.append((start, end, variant))

    return buckets


def evaluate_flag(feature_flag: FeatureFlag, identifier_data):
    """
    Outputs the feature flag variant value assigned to the user based on the identifier data
    """

    identifier_override_field = rollout_identifier_to_override_string(
        feature_flag.rollout_identifier
    )
    identifier = get_identifier(feature_flag, identifier_data)

    # check for overrides
    override_variant = get_override_variant(
        feature_flag, identifier, identifier_override_field
    )
    if override_variant:
        return override_variant.value

    if feature_flag.proportion == 1.0 and len(feature_flag.variants.all()) == 1:
        # skip the hashing and just return its value
        return feature_flag.variants.first().value

    key = mmh3.hash128(feature_flag.name + str(identifier) + feature_flag.salt)
    buckets = compute_buckets(feature_flag)

    for bucket_start, bucket_end, variant in buckets:
        if bucket_start <= key and key < bucket_end:
            return variant.value

    return False  # make default something to define in django admin
