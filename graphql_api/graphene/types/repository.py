from graphene import relay
from graphene_django import DjangoObjectType

from core.models import Repository


class RepositoryType(DjangoObjectType):
    class Meta:
        model = Repository
        fields = ("name", "private", "active")
        interfaces = (relay.Node,)
