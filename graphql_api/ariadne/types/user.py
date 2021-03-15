from ariadne import ObjectType

user = """
    type User {
        username: String!
        name: String
        avatarUrl: String
        student: Boolean!
    }
"""

user_bindable = ObjectType("User")

@user_bindable.field("avatarUrl")
def resolve_avatar_url(user, info):
    return user.avatar_url
