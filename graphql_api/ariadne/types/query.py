from ariadne import ObjectType

query = """
    type Query {
        me: Me
    }
"""

query_bindable = ObjectType("Query")

@query_bindable.field("me")
def resolve_me(_, info):
    user = info.context['request'].user
    if not user.is_authenticated:
        return None
    return user
