import graphene
from .types.query import Query

schema = graphene.Schema(query=Query)
