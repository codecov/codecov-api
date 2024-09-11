from unittest.mock import MagicMock, patch

import jwt

from codecov_auth.views.okta import OKTA_BASIC_AUTH, OktaLoginView
from codecov_auth.views.okta_mixin import validate_id_token

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
        "codecov_auth.views.okta_mixin.requests.get",
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

    id_payload = validate_id_token(
        iss="https://example.okta.com", id_token=id_token, client_id="test-client-id"
    )
    assert id_payload.sub == "test-okta-id"
    assert id_payload.name == "Some User"
    assert id_payload.email == "test@example.com"

    get_keys.assert_called_once_with("https://example.okta.com/oauth2/v1/keys")


def test_okta_fetch_user_data_invalid_state(client, db):
    with patch("codecov_auth.views.okta_mixin.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        with patch.object(OktaLoginView, "verify_state", return_value=False):
            view = OktaLoginView()
            res = view._fetch_user_data(
                "https://example.okta.com",
                "test-code",
                "invalid-state",
                "https://localhost:8000/login/okta",
                OKTA_BASIC_AUTH,
            )

    assert res is None
