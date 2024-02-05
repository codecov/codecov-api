from shared.rollouts import Feature

from codecov_auth.models import Owner


def owner_slug(owner: Owner) -> str:
    return f"{owner.service}/{owner.username}"


TEST_RESULTS_UPLOAD_FEATURE_BY_OWNER_SLUG = Feature(
    "test_results_upload",
    0.0,
    overrides={
        "github/codecov": "enabled",
        "bitbucket/codecov": "enabled",
        "gitlab/codecov": "enabled",
    },
)
