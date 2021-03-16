from graphene import relay
from graphene_django import DjangoObjectType, DjangoConnectionField

from codecov_auth.models import Owner
from core.models import Repository
from graphql_api.actions.repository import list_repository_for_owner
from .repository import RepositoryType

class OwnerType(DjangoObjectType):

    class Meta:
        model = Owner
        fields = ("username",)
        interfaces = (relay.Node,)

    repositories = DjangoConnectionField(RepositoryType)

    def resolve_repositories(self, info, *args, **kwargs):
        current_user = info.context.user
        return list_repository_for_owner(current_user, self)
