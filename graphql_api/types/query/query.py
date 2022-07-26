from ariadne import ObjectType
from django.conf import settings

from graphql_api.actions.owner import get_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.types.enums.enums import LoginProvider

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")


@query_bindable.field("me")
def resolve_me(_, info):
    user = info.context["request"].user
    if not user.is_authenticated:
        return None
    return user


@query_bindable.field("owner")
def resolve_owner(_, info, username):
    service = info.context["service"]
    return get_owner(service, username)


@query_bindable.field("loginProviders")
def resolve_login_providers(_, info):
    login_providers = []
    if settings.GITHUB_CLIENT_ID:
        login_providers.append(LoginProvider("github"))

    if settings.GITHUB_ENTERPRISE_CLIENT_ID:
        login_providers.append(LoginProvider("github_enterprise"))

    if settings.GITLAB_CLIENT_ID:
        login_providers.append(LoginProvider("gitlab"))

    if settings.GITLAB_ENTERPRISE_CLIENT_ID:
        login_providers.append(LoginProvider("gitlab_enterprise"))

    if settings.BITBUCKET_CLIENT_ID:
        login_providers.append(LoginProvider("bitbucket"))

    if settings.BITBUCKET_SERVER_CLIENT_ID:
        login_providers.append(LoginProvider("bitbucket_server"))

    return login_providers
