from ariadne import ObjectType

from codecov_auth.models import UserToken

user_token_bindable = ObjectType("UserToken")


@user_token_bindable.field("id")
def resolve_token(user_token: UserToken, info):
    return user_token.external_id


@user_token_bindable.field("type")
def resolve_token(user_token: UserToken, info):
    return user_token.token_type


@user_token_bindable.field("lastFour")
def resolve_token(user_token: UserToken, info):
    return str(user_token.token)[-4:]


@user_token_bindable.field("expiration")
def resolve_expiration(user_token: UserToken, info):
    return user_token.valid_until
