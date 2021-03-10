from django.urls import path
from ariadne.contrib.django.views import GraphQLView as AriadneView
from graphene_django.views import GraphQLView as GrapheneView
from django.conf import settings

from .ariadne import schema as ariadne_schema
from .graphene import schema as graphene_schema

urlpatterns = [
    path('ariadne', AriadneView.as_view(schema=ariadne_schema), name='graphql'),
    path("graphene", GrapheneView.as_view(schema=graphene_schema, graphiql=settings.DEBUG)),
]
