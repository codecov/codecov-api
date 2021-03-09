import graphene

class Query(graphene.ObjectType):
    hello = graphene.String(default_value="hi")

schema = graphene.Schema(query=Query)
