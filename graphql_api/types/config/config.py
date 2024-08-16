from typing import List, Optional

from ariadne import ObjectType
from distutils.util import strtobool
from django.conf import settings
from graphql.type.definition import GraphQLResolveInfo

import services.self_hosted as self_hosted
from codecov.db import sync_to_async
from graphql_api.types.enums.enums import LoginProvider, SyncProvider

config_bindable = ObjectType("Config")


@config_bindable.field("loginProviders")
def resolve_login_providers(_, info) -> List[str]:
    login_providers = []

    if not settings.DISABLE_GIT_BASED_LOGIN:
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

    if settings.OKTA_OAUTH_CLIENT_ID:
        login_providers.append(LoginProvider("okta"))

    return login_providers


@config_bindable.field("syncProviders")
def resolve_sync_providers(_, info) -> List[str]:
    sync_providers = []

    if settings.GITHUB_CLIENT_ID:
        sync_providers.append(SyncProvider("github"))

    if settings.GITHUB_ENTERPRISE_CLIENT_ID:
        sync_providers.append(SyncProvider("github_enterprise"))

    if settings.GITLAB_CLIENT_ID:
        sync_providers.append(SyncProvider("gitlab"))

    if settings.GITLAB_ENTERPRISE_CLIENT_ID:
        sync_providers.append(SyncProvider("gitlab_enterprise"))

    if settings.BITBUCKET_CLIENT_ID:
        sync_providers.append(SyncProvider("bitbucket"))

    if settings.BITBUCKET_SERVER_CLIENT_ID:
        sync_providers.append(SyncProvider("bitbucket_server"))

    return sync_providers


@config_bindable.field("planAutoActivate")
@sync_to_async
def resolve_plan_auto_activate(_, info: GraphQLResolveInfo) -> Optional[bool]:
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.is_autoactivation_enabled()


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


@config_bindable.field("selfHostedLicense")
def resolve_self_hosted_license(_, info):
    if not settings.IS_ENTERPRISE:
        return None
    license = self_hosted.get_current_license()

    if not license.is_valid:
        return None

    return license


@config_bindable.field("hasAdmins")
def resolve_has_admins(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    return len(settings.ADMINS_LIST) != 0


@config_bindable.field("githubEnterpriseURL")
def resolve_github_enterprise_url(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    if settings.GITHUB_ENTERPRISE_CLIENT_ID:
        return settings.GITHUB_ENTERPRISE_URL


@config_bindable.field("gitlabEnterpriseURL")
def resolve_gitlab_enterprise_url(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    if settings.GITLAB_ENTERPRISE_CLIENT_ID:
        return settings.GITLAB_ENTERPRISE_URL


@config_bindable.field("bitbucketServerURL")
def resolve_bitbucket_server_url(_, info):
    if not settings.IS_ENTERPRISE:
        return None

    if settings.BITBUCKET_SERVER_CLIENT_ID:
        return settings.BITBUCKET_SERVER_URL
