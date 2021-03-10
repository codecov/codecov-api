from ariadne import ObjectType

me = """
    type Me {
        user: User!
    }
"""

me_bindable = ObjectType("Me")

@me_bindable.field("user")
def resolve_user(user, info):
    return user
