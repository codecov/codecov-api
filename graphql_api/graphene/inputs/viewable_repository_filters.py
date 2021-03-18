import graphene

class ViewableRepositoryFilters(graphene.InputObjectType):
    term = graphene.String(required=False)
