import base64
import hashlib
import hmac
import time

import requests
from django.conf import settings
from rest_framework import exceptions

from codecov_auth.constants import GITLAB_BASE_URL

GITLAB_PAYLOAD_AVATAR_URL_KEY = "avatar_url"


def get_gitlab_url(email, size):
    res = requests.get(
        "{}/api/v4/avatar?email={}&size={}".format(GITLAB_BASE_URL, email, size)
    )
    url = ""
    if res.status_code == 200:
        data = res.json()
        try:
            url = data[GITLAB_PAYLOAD_AVATAR_URL_KEY]
        except KeyError:
            pass

    return url


DEFAULT_SIGNED_VALUE_VERSION = 2


def create_signed_value(name, value, version=None):
    """
    Signs and timestamps a string so it cannot be forged.
    This is the function that we should call to generate signed cookies in a way that
        tornado also understands
    Implementation heavily from https://github.com/tornadoweb/tornado/blob/v4.5.2/tornado/web.py
    """
    secret = settings.COOKIE_SECRET
    if version is None:
        version = DEFAULT_SIGNED_VALUE_VERSION
    if version != DEFAULT_SIGNED_VALUE_VERSION:
        raise Exception("Unsupported version of signed cookie")
    return do_create_signed_value_v2(secret, name, value, version=version)


def do_create_signed_value_v2(secret, name, value, version=None, clock=None):
    """
    Implementation to sign a cookie in a way that is compatible with tornado==4.5.2
    Implementation heavily from https://github.com/tornadoweb/tornado/blob/v4.5.2/tornado/web.py

    We are here dropping the "dict key" implementation from the tornado implemenation,
        which allows for versioning of the key. This might be wanted in the future,
        it just doesn't match our infra
    """
    if clock is None:
        clock = time.time

    timestamp = str(int(clock()))
    value = base64.b64encode(value.encode()).decode()

    def format_field(s):
        return f"{len(s)}:{s}"

    key_version = None

    to_sign = "|".join(
        [
            "2",
            format_field(str(key_version or 0)),
            format_field(timestamp),
            format_field(name),
            format_field(value),
            "",
        ]
    )

    signature = create_signature_v2(secret, to_sign)
    return to_sign + signature


def create_signature_v2(secret: str, s: str) -> str:
    hash_value = hmac.new(secret.encode(), digestmod=hashlib.sha256)
    hash_value.update(s.encode())
    return hash_value.hexdigest()


def decode_token_from_cookie(secret, encoded_cookie):
    """
    From a cookie, extracts the original value meant from it.
    Raises `exceptions.AuthenticationFailed` if the cookie does not have the proper format.
    Ideally, this code is such that:

        ```
        decode_token_from_cookie(secret, do_create_signed_value_v2(secret, name, value)) == value
        ```
    """
    cookie_fields = encoded_cookie.split("|")
    if len(cookie_fields) < 6:
        raise exceptions.AuthenticationFailed("No correct token format")
    cookie_value, cookie_signature = "|".join(cookie_fields[:5]) + "|", cookie_fields[5]
    expected_sig = create_signature_v2(secret, cookie_value)
    if not hmac.compare_digest(cookie_signature, expected_sig):
        raise exceptions.AuthenticationFailed("Signature doesnt match")
    splitted = cookie_fields[4].split(":")
    if len(splitted) != 2:
        raise exceptions.AuthenticationFailed("No correct token format")
    _, encoded_token = splitted
    return base64.b64decode(encoded_token).decode()


def current_user_part_of_org(current_user, org):
    if not current_user.is_authenticated:
        return False
    if current_user == org:
        return True
    # user is a direct member of the org
    orgs_of_user = current_user.organizations or []
    return org.ownerid in orgs_of_user
