from base64 import b64decode

from codecov_auth.models import Session
from rest_framework import authentication
from rest_framework import exceptions


class CodecovSessionAuthentication(authentication.BaseAuthentication):
    """Authenticates based on the user cookie from the old codecov.io tornado system

    This Authenticator works based on the existing authentication method from the current/old
        codecov.io codebase. On tornado, the `set_secure_cookie` writes a base64 encoded
        value for the cookie, along with some metadata and a signature in the end.

    In this context we are not interested in the signature, since it will require a lot of
        code porting from tornado and it is not that beneficial for our code.

    Steps:

        The cookie comes in the format:

            2|1:0|10:1546487835|12:github-token|48:MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh|f520039bc6cfb111e4cfc5c3e44fc4fa5921402918547b54383939da803948f4

        We then parse it and take the 5th pipe-delimited value

            48:MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh

        This is the length + the field itself

            MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh

        We base64 decode it and obtain

            06ed406d-3fe5-4ff4-baba-349739732b6a

        Which is the final token

    """

    def authenticate(self, request):
        authorization = request.META.get('HTTP_AUTHORIZATION', '')
        if not authorization or ' ' not in authorization:
            return None
        val, encoded_cookie = authorization.split(' ')
        if val != 'frontend':
            return None
        token = self.decode_token_from_cookie(encoded_cookie)
        try:
            session = Session.objects.get(token=token)
        except Session.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')
        return (session.owner, session)

    def decode_token_from_cookie(self, encoded_cookie):
        cookie_fields = encoded_cookie.split('|')
        if len(cookie_fields) < 5:
            raise exceptions.AuthenticationFailed('No correct token format')
        splitted = cookie_fields[4].split(':')
        if len(splitted) != 2:
            raise exceptions.AuthenticationFailed('No correct token format')
        _, encoded_token = splitted
        return b64decode(encoded_token).decode()
