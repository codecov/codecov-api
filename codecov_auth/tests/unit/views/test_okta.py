from http.cookies import SimpleCookie

import jwt
import pytest
from django.conf import settings
from django.contrib import auth
from django.test import override_settings
from django.urls import reverse

from codecov_auth.models import OktaUser
from codecov_auth.tests.factories import OktaUserFactory, OwnerFactory, UserFactory
from codecov_auth.views.okta import auth as okta_basic_auth
from codecov_auth.views.okta import validate_id_token


@pytest.fixture
def mocked_okta_token_request(mocker):
    return mocker.patch(
        "codecov_auth.views.okta.requests.post",
        return_value=mocker.MagicMock(
            status_code=200,
            json=mocker.MagicMock(
                return_value={
                    "access_token": "test-access-token",
                    "refresh_token": "test-refresh-token",
                    "id_token": "test-id-token",
                }
            ),
        ),
    )


@pytest.fixture
def mocked_validate_id_token(mocker):
    return mocker.patch(
        "codecov_auth.views.okta.validate_id_token",
        return_value={
            "sub": "test-id",
            "email": "test@example.com",
            "name": "Some User",
        },
    )


# random keypair for RS256 JWTs used below
public_key = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAu1SU1LfVLPHCozMxH2Mo
4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u
+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyeh
kd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ
0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdg
cKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbc
mwIDAQAB
-----END PUBLIC KEY-----
"""
private_key = """-----BEGIN PRIVATE KEY-----
MIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQC7VJTUt9Us8cKj
MzEfYyjiWA4R4/M2bS1GB4t7NXp98C3SC6dVMvDuictGeurT8jNbvJZHtCSuYEvu
NMoSfm76oqFvAp8Gy0iz5sxjZmSnXyCdPEovGhLa0VzMaQ8s+CLOyS56YyCFGeJZ
qgtzJ6GR3eqoYSW9b9UMvkBpZODSctWSNGj3P7jRFDO5VoTwCQAWbFnOjDfH5Ulg
p2PKSQnSJP3AJLQNFNe7br1XbrhV//eO+t51mIpGSDCUv3E0DDFcWDTH9cXDTTlR
ZVEiR2BwpZOOkE/Z0/BVnhZYL71oZV34bKfWjQIt6V/isSMahdsAASACp4ZTGtwi
VuNd9tybAgMBAAECggEBAKTmjaS6tkK8BlPXClTQ2vpz/N6uxDeS35mXpqasqskV
laAidgg/sWqpjXDbXr93otIMLlWsM+X0CqMDgSXKejLS2jx4GDjI1ZTXg++0AMJ8
sJ74pWzVDOfmCEQ/7wXs3+cbnXhKriO8Z036q92Qc1+N87SI38nkGa0ABH9CN83H
mQqt4fB7UdHzuIRe/me2PGhIq5ZBzj6h3BpoPGzEP+x3l9YmK8t/1cN0pqI+dQwY
dgfGjackLu/2qH80MCF7IyQaseZUOJyKrCLtSD/Iixv/hzDEUPfOCjFDgTpzf3cw
ta8+oE4wHCo1iI1/4TlPkwmXx4qSXtmw4aQPz7IDQvECgYEA8KNThCO2gsC2I9PQ
DM/8Cw0O983WCDY+oi+7JPiNAJwv5DYBqEZB1QYdj06YD16XlC/HAZMsMku1na2T
N0driwenQQWzoev3g2S7gRDoS/FCJSI3jJ+kjgtaA7Qmzlgk1TxODN+G1H91HW7t
0l7VnL27IWyYo2qRRK3jzxqUiPUCgYEAx0oQs2reBQGMVZnApD1jeq7n4MvNLcPv
t8b/eU9iUv6Y4Mj0Suo/AU8lYZXm8ubbqAlwz2VSVunD2tOplHyMUrtCtObAfVDU
AhCndKaA9gApgfb3xw1IKbuQ1u4IF1FJl3VtumfQn//LiH1B3rXhcdyo3/vIttEk
48RakUKClU8CgYEAzV7W3COOlDDcQd935DdtKBFRAPRPAlspQUnzMi5eSHMD/ISL
DY5IiQHbIH83D4bvXq0X7qQoSBSNP7Dvv3HYuqMhf0DaegrlBuJllFVVq9qPVRnK
xt1Il2HgxOBvbhOT+9in1BzA+YJ99UzC85O0Qz06A+CmtHEy4aZ2kj5hHjECgYEA
mNS4+A8Fkss8Js1RieK2LniBxMgmYml3pfVLKGnzmng7H2+cwPLhPIzIuwytXywh
2bzbsYEfYx3EoEVgMEpPhoarQnYPukrJO4gwE2o5Te6T5mJSZGlQJQj9q4ZB2Dfz
et6INsK0oG8XVGXSpQvQh3RUYekCZQkBBFcpqWpbIEsCgYAnM3DQf3FJoSnXaMhr
VBIovic5l0xFkEHskAjFTevO86Fsz1C2aSeRKSqGFoOQ0tmJzBEs1R6KqnHInicD
TQrKhArgLXX4v3CddjfTRJkFWDbE/CkvKZNOrcf1nhaGCPspRJj2KUkj1Fhl9Cnc
dn/RsYEONbwQSjIfMPkvxF+8HQ==
-----END PRIVATE KEY-----
"""


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
)
def test_validate_id_token(mocker):
    data = {
        "sub": "test-okta-id",
        "name": "Some User",
        "email": "test@example.com",
        "iss": "https://example.okta.com",
        "aud": "test-client-id",
    }
    id_token = jwt.encode(
        data, private_key, algorithm="RS256", headers={"kid": "test-kid"}
    )

    # did this offline so as not to need an additional dependency - here's the code
    # if we ever need to regenerate this:
    #
    # from Crypto.PublicKey import RSA
    # import base64
    # pub = RSA.importKey(public_key)
    # modulus = base64.b64encode(pub.n.to_bytes(256, "big")).decode("ascii")
    # exponent = base64.b64encode(pub.e.to_bytes(3, "big")).decode("ascii")

    exponent = "AQAB"
    modulus = "u1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gunVTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxKLxoS2tFczGkPLPgizskuemMghRniWaoLcyehkd3qqGElvW/VDL5AaWTg0nLVkjRo9z+40RQzuVaE8AkAFmxZzow3x+VJYKdjykkJ0iT9wCS0DRTXu269V264Vf/3jvredZiKRkgwlL9xNAwxXFg0x/XFw005UWVRIkdgcKWTjpBP2dPwVZ4WWC+9aGVd+Gyn1o0CLelf4rEjGoXbAAEgAqeGUxrcIlbjXfbcmw=="

    get_keys = mocker.patch(
        "codecov_auth.views.okta.requests.get",
        return_value=mocker.MagicMock(
            status_code=200,
            json=mocker.MagicMock(
                return_value={
                    "keys": [
                        {
                            "kty": "RSA",
                            "alg": "RS256",
                            "kid": "test-kid",
                            "use": "sig",
                            "e": exponent,
                            "n": modulus,
                        }
                    ]
                }
            ),
        ),
    )

    id_payload = validate_id_token(iss="https://example.okta.com", id_token=id_token)
    assert id_payload["sub"] == "test-okta-id"
    assert id_payload["name"] == "Some User"
    assert id_payload["email"] == "test@example.com"

    get_keys.assert_called_once_with("https://example.okta.com/oauth2/v1/keys")


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_redirect_to_authorize(client):
    res = client.get(
        reverse("okta-login"),
        data={
            "iss": "https://example.okta.com",
        },
    )
    assert res.status_code == 302
    assert (
        res.url
        == "https://example.okta.com/oauth2/v1/authorize?response_type=code&client_id=test-client-id&scope=openid+email+profile&redirect_uri=https%3A%2F%2Flocalhost%3A8000%2Flogin%2Fokta&state=https%3A%2F%2Fexample.okta.com"
    )


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_redirect_to_authorize_no_iss(client):
    res = client.get(reverse("okta-login"))
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_redirect_to_authorize_invalid_iss(client):
    res = client.get(reverse("okta-login"), data={"iss": "https://non.okta.domain"})
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    mocked_okta_token_request.assert_called_once_with(
        "https://example.okta.com/oauth2/v1/token",
        auth=okta_basic_auth,
        data={
            "grant_type": "authorization_code",
            "code": "test-code",
            "redirect_uri": "https://localhost:8000/login/okta",
        },
    )

    mocked_validate_id_token.assert_called_once_with(
        "https://example.okta.com",
        "test-id-token",
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    okta_user = OktaUser.objects.get(okta_id="test-id")
    assert okta_user.access_token == "test-access-token"
    assert okta_user.email == "test@example.com"
    assert okta_user.name == "Some User"
    user = okta_user.user
    assert user is not None
    assert user.email == okta_user.email
    assert user.name == okta_user.name

    # logs in new user
    current_user = auth.get_user(client)
    assert user == current_user


def test_okta_perform_login_missing_cookie(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"

    # does not login user
    assert auth.get_user(client).is_anonymous


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_authenticated(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    user = UserFactory()
    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    client.force_login(user=user)
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # creates new user records
    okta_user = OktaUser.objects.get(okta_id="test-id")
    assert okta_user.access_token == "test-access-token"
    assert okta_user.email == "test@example.com"
    assert okta_user.name == "Some User"
    assert okta_user.user == user

    # leaves user logged in
    current_user = auth.get_user(client)
    assert user == current_user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_existing_okta_user(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    okta_user = OktaUserFactory(okta_id="test-id")

    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_authenticated_existing_okta_user(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    okta_user = OktaUserFactory(okta_id="test-id")
    other_okta_user = OktaUserFactory()

    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    client.force_login(user=other_okta_user.user)
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/sync"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_existing_okta_user_existing_owner(
    client, mocked_okta_token_request, mocked_validate_id_token, db
):
    okta_user = OktaUserFactory(okta_id="test-id")
    OwnerFactory(service="github", user=okta_user.user)

    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    # redirects to service page
    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/gh"

    # logs in Okta user
    current_user = auth.get_user(client)
    assert current_user == okta_user.user


@override_settings(
    OKTA_OAUTH_CLIENT_ID="test-client-id",
    OKTA_OAUTH_CLIENT_SECRE="test-client-secret",
    OKTA_OAUTH_REDIRECT_URL="https://localhost:8000/login/okta",
)
def test_okta_perform_login_error(client, mocker, db):
    mocker.patch(
        "codecov_auth.views.okta.requests.post",
        return_value=mocker.MagicMock(
            status_code=401,
        ),
    )

    client.cookies = SimpleCookie({"_okta_iss": "https://example.okta.com"})
    res = client.get(
        reverse("okta-login"),
        data={
            "code": "test-code",
        },
    )

    assert res.status_code == 302
    assert res.url == f"{settings.CODECOV_DASHBOARD_URL}/login"
