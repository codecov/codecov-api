from distutils.util import strtobool

from ariadne import ObjectType
from asgiref.sync import sync_to_async
from django.conf import settings

import services.self_hosted as self_hosted
from graphql_api.types.enums.enums import LoginProvider

config_bindable = ObjectType("Config")


@config_bindable.field("loginProviders")
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


@config_bindable.field("seatsUsed")
@sync_to_async
def resolve_seats_used(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.activated_owners().count()


@config_bindable.field("seatsLimit")
@sync_to_async
def resolve_seats_limit(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.license_seats()


@config_bindable.field("isTimescaleEnabled")
@sync_to_async
def resolve_is_timescale_enabled(_, info):
    if isinstance(settings.TIMESERIES_ENABLED, str):
        return bool(strtobool(settings.TIMESERIES_ENABLED))

    return settings.TIMESERIES_ENABLED

@config_bindable.field("hasAdmins")
def resolve_has_admins(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    return len(settings.ADMINS_LIST) != 0
