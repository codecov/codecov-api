import logging
from typing import Optional

import jwt
from django.conf import settings
from django.db.utils import IntegrityError

from codecov_auth.models import Owner

log = logging.getLogger(__name__)


class SentryError(Exception):
    pass


class SentryInvalidStateError(SentryError):
    """
    The Sentry `state` JWT was malformed or not signed properly.
    """

    pass


class SentryUserAlreadyExistsError(SentryError):
    """
    The Sentry `user_id` was already claimed by a Codecov owner.
    """

    pass


def decode_state(state: str) -> Optional[dict]:
    """
    Decode the given state (a JWT) using our shared secret.
    Returns `None` if the state could not be decoded.
    """
    secret = settings.SENTRY_JWT_SHARED_SECRET
    try:
        return jwt.decode(state, secret, algorithms=["HS256"])
    except jwt.exceptions.InvalidSignatureError:
        # signed with a different secret
        log.error(
            "Sentry state has invalid signature",
            extra=dict(sentry_state=state),
        )
        return None
    except jwt.exceptions.DecodeError:
        # malformed JWT
        log.error(
            "Sentry state is malformed",
            extra=dict(sentry_state=state),
        )
        return None


def save_sentry_state(owner: Owner, state: str):
    """
    If the given state decodes successfully then save it with the owner.
    """
    decoded_state = decode_state(state)
    if decoded_state is None:
        log.error(
            "Invalid Sentry state", extra=dict(owner_id=owner.pk, sentry_state=state)
        )
        raise SentryInvalidStateError()

    sentry_user_id = decoded_state.get("user_id")
    if sentry_user_id is not None:
        owner.sentry_user_id = sentry_user_id
    owner.sentry_user_data = decoded_state

    try:
        owner.save()
    except IntegrityError:
        log.error(
            "Sentry user already exists",
            extra=dict(
                owner_id=owner.pk,
                sentry_user_id=sentry_user_id,
                sentry_user_data=decoded_state,
            ),
        )
        raise SentryUserAlreadyExistsError()


def is_sentry_user(owner: Owner) -> bool:
    """
    Returns true if the given owner has been linked with a Sentry user.
    """
    return owner.sentry_user_id is not None
