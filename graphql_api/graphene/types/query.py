import graphene

from .me import MeType


class Query(graphene.ObjectType):
    me = graphene.Field(MeType)

    def resolve_me(self, info):
        if not info.context.user.is_authenticated:
            return None
        return info.context.user
