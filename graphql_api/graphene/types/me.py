import graphene

from .user import OwnerType


class MeType(graphene.ObjectType):
    user = graphene.Field(OwnerType)

    def resolve_user(self, info):
        # self is the current authenticated user
        return self
