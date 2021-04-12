from ariadne.contrib.django.views import GraphQLView as BaseAriadneView
from django.conf import settings

from codecov_auth.authentication import CodecovTokenAuthentication


class AriadneView(BaseAriadneView):
    graphiql = settings.DEBUG

    def authenticate(self, request):
        try:
            auth = CodecovTokenAuthentication().authenticate(request)
            if auth:
                request.user = auth[0]
        except:
            # we make authentication fail silently
            pass

    def dispatch(self, request, *args, **kwargs):
        self.authenticate(request)
        return super().dispatch(request, *args, **kwargs)
