import graphene

from .user import UserType
from .owner import OwnerType


class MeType(graphene.ObjectType):
    user = graphene.Field(UserType)
    owner = graphene.Field(OwnerType)

    def resolve_user(self, info):
        # self is the current authenticated user
        return self

    def resolve_owner(self, info):
        # self is the current authenticated user, which is also a owner 
        return self
