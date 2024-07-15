import json
import logging
import re
from urllib.parse import urlencode

import jwt
import pydantic
import requests
from django.http import HttpResponse
from django.shortcuts import redirect
from requests.auth import HTTPBasicAuth

from codecov_auth.views.base import StateMixin

log = logging.getLogger(__name__)

ISS_REGEX = re.compile(r"https://[\w\d\-\_]+.okta.com/?")


class OktaTokenResponse(pydantic.BaseModel):
    """This model serializes the response from Okta's oauth/v1/token endpoint.
    ref: https://developer.okta.com/docs/reference/api/oidc/#token

    Keeping reference to only the fields that are used.
    """

    access_token: str
    id_token: str  # this will be present since we requested the `oidc` scope


class OktaIdTokenPayload(pydantic.BaseModel):
    """Serializes the ID Payload from Okta's id_token deserialization.
    ref: https://developer.okta.com/docs/reference/api/oidc/#id-token
    """

    aud: str
    iss: str
    sub: str
    email: str
    name: str


def validate_id_token(iss: str, id_token: str, client_id: str) -> OktaIdTokenPayload:
    res = requests.get(f"{iss}/oauth2/v1/keys")
    jwks = res.json()

    public_keys = {}
    for jwk in jwks["keys"]:
        kid = jwk["kid"]
        public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    kid = jwt.get_unverified_header(id_token)["kid"]
    key = public_keys[kid]

    id_payload = jwt.decode(
        id_token,
        key=key,
        algorithms=["RS256"],
        audience=client_id,
    )
    id_token_payload = OktaIdTokenPayload(**id_payload)
    assert id_token_payload.iss == iss
    assert id_token_payload.aud == client_id

    return id_token_payload


class OktaLoginMixin(StateMixin):
    def _fetch_user_data(
        self,
        iss: str,
        code: str,
        state: str,
        redirect_url: str,
        auth: HTTPBasicAuth,
    ) -> OktaTokenResponse | None:
        res = requests.post(
            f"{iss}/oauth2/v1/token",
            auth=auth,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_url,
                "state": state,
            },
        )

        if not self.verify_state(state):
            log.warning("Invalid state during Okta OAuth")
            return None

        if res.status_code >= 400:
            return None

        return OktaTokenResponse(**res.json())

    def _redirect_to_consent(
        self, iss: str, client_id: str, oauth_redirect_url: str
    ) -> HttpResponse:
        state = self.generate_state()
        qs = urlencode(
            dict(
                response_type="code",
                client_id=client_id,
                scope="openid email profile",
                redirect_uri=oauth_redirect_url,
                state=state,
            )
        )
        redirect_url = f"{iss}/oauth2/v1/authorize?{qs}"
        response = redirect(redirect_url)
        return response
