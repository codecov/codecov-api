from ariadne.contrib.django.views import GraphQLView as BaseAriadneView
from graphene_django.views import GraphQLView as BaseGrapheneView
from django.conf import settings

from codecov_auth.authentication import CodecovTokenAuthentication
from .ariadne import schema as ariadne_schema
from .graphene import schema as graphene_schema


class AuthenticateMixin:

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


class GrapheneView(AuthenticateMixin, BaseGrapheneView):
    pass


class AriadneView(AuthenticateMixin, BaseAriadneView):
    graphiql = settings.DEBUG
