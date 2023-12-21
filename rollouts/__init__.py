from shared.rollouts import Feature

from codecov_auth.models import Owner


def owner_slug(owner: Owner) -> str:
    return f"{owner.service}/{owner.username}"


# By default, features have one variant:
#    { "enabled": FeatureVariant(True, 1.0) }
TOKENLESS_AUTH_BY_OWNER_SLUG = Feature(
    "tokenless_auth",
    0.0,
    overrides={
        "github/codecov": "enabled",
        "github/thomasrockhu-codecov": "enabled",
        "github/giovanni-guidini": "enabled",
    },
)
