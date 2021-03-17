import graphene
from graphene_django import DjangoConnectionField

from graphql_api.actions.repository import search_repos
from graphql_api.actions.owner import search_my_owners
from .user import UserType
from .owner import OwnerType
from .repository import RepositoryType
from ..inputs.viewable_repository_filters import ViewableRepositoryFilters
from ..inputs.my_organization_filters import MyOrganizationFilters


class ViewableRepositoriesConnection(DjangoConnectionField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("filters", ViewableRepositoryFilters())
        return super().__init__(*args, **kwargs)


class MyOrganizationConnection(DjangoConnectionField):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("filters", MyOrganizationFilters())
        return super().__init__(*args, **kwargs)


class MeType(graphene.ObjectType):
    user = graphene.Field(UserType)
    owner = graphene.Field(OwnerType)
    viewable_repositories = ViewableRepositoriesConnection(RepositoryType)
    my_organizations = MyOrganizationConnection(OwnerType)

    def resolve_user(current_user, info):
        return current_user

    def resolve_owner(current_user, info):
        return current_user

    def resolve_viewable_repositories(current_user, info, *args, **kwargs):
        return search_repos(current_user, kwargs.get('filters', {}))

    def resolve_my_organizations(current_user, info, *args, **kwargs):
        return search_my_owners(current_user, kwargs.get('filters', {}))
