from django.urls import path
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from .ariadne import schema as ariadne_schema
from .graphene import schema as graphene_schema


from .views import  GrapheneView, AriadneView

urlpatterns = [
    path('<str:service>/ariadne', csrf_exempt(AriadneView.as_view(schema=ariadne_schema)), name='graphql'),
    path('<str:service>/graphene', GrapheneView.as_view(schema=graphene_schema, graphiql=settings.DEBUG)),
]
