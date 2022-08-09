import jwt
from ariadne import ObjectType
from django.conf import settings

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

user = ariadne_load_local_graphql(__file__, "user.graphql")

user_bindable = ObjectType("User")


@user_bindable.field("cannySSOToken")
def resolve_canny_sso_token(user, info):
    name = user.username
    if user.name:
        name = user.name

    user_data = {
        "avatarURL": user.avatar_url,
        "email": user.email,
        "id": user.ownerid,
        "name": name,
    }
    return jwt.encode(user_data, settings.CANNY_SSO_PRIVATE_TOKEN, algorithm="HS256")
