from shared.rollouts import Feature

from codecov_auth.models import Owner


def owner_slug(owner: Owner) -> str:
    return f"{owner.service}/{owner.username}"


__all__ = ["Feature"]

NO_PREPROCESS_UPLOAD = Feature("no_PreProcessUpload")


# By default, features have one variant:
#    { "enabled": FeatureVariant(True, 1.0) }
