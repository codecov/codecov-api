import graphene

class MyOrganizationFilters(graphene.InputObjectType):
    term = graphene.String(required=False)
