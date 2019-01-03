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
        val, token = authorization.split(' ')
        if val != 'token':
            return None
        try:
            session = Session.objects.get(token=token)
        except Session.DoesNotExist:
            raise exceptions.AuthenticationFailed('No such user')
        return (session.owner, session)
