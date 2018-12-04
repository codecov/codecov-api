from rest_framework import authentication
from rest_framework import exceptions

from codecov_auth.models import Session


class CodecovAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        for service_name in self.available_services():
            cookie_name = f"{service_name}-token"
            cookie_value = request.META.get(cookie_name)
            if cookie_value:
                try:
                    session = Session.objects.get(oauth_token=cookie_value)
                    user = session.ownerid
                except Exception:
                    raise exceptions.AuthenticationFailed('No such user')
                return (user, cookie_value)

    def available_services(self):
        return ['github', 'gitlab', 'bitbucket']
