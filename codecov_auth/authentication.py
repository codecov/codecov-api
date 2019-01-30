from base64 import b64decode

from codecov_auth.models import Session
from rest_framework import authentication
from rest_framework import exceptions


class CodecovSessionAuthentication(authentication.BaseAuthentication):

    def authenticate(self, request):
        authorization = request.META.get('HTTP_AUTHORIZATION', '')
        if not authorization:
            return None
        if ' ' not in authorization:
            return None
        val, encoded_cookie = authorization.split(' ')
        if val != 'frontend':
            return None
        cookie_fields = encoded_cookie.split('|')
        if len(cookie_fields) < 5:
            raise exceptions.AuthenticationFailed('No correct token format')
        splitted = cookie_fields[4].split(':')
        if len(splitted) != 2:
            raise exceptions.AuthenticationFailed('No correct token format')
        _, encoded_token = splitted
        token = b64decode(encoded_token).decode()
        print(token)
        try:
            session = Session.objects.get(token=token)
        except Session.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')
        return (session.owner, session)
