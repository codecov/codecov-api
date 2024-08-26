from codecov_auth.models import Owner


def owner_slug(owner: Owner) -> str:
    return f"{owner.service}/{owner.username}"
