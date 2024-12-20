from typing import Any, Optional

from ariadne import ObjectType
from django.conf import settings
from graphql import GraphQLResolveInfo
from sentry_sdk import Scope

from codecov.commands.exceptions import UnauthorizedGuestAccess
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from graphql_api.actions.owner import get_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")


def query_name(info: GraphQLResolveInfo) -> Optional[str]:
    if info.operation and info.operation.name:
        return info.operation.name.value


def configure_sentry_scope(query_name: Optional[str]) -> None:
    # this sets the Sentry transaction name to the GraphQL query name which
    # should make it easier to search/filter transactions
    # we're configuring this here since it's the main entrypoint into GraphQL resolvers

    # https://docs.sentry.io/platforms/python/enriching-events/transaction-name/
    scope = Scope.get_current_scope()
    if scope.transaction:
        scope.transaction.name = f"GraphQL [{query_name}]"


@query_bindable.field("me")
@sync_to_async
def resolve_me(_: Any, info: GraphQLResolveInfo) -> Optional[Owner]:
    configure_sentry_scope(query_name(info))
    # will be `None` for anonymous users or users w/ no linked owners
    return info.context["request"].current_owner


@query_bindable.field("owner")
async def resolve_owner(
    _: Any, info: GraphQLResolveInfo, username: str
) -> Optional[Owner]:
    configure_sentry_scope(query_name(info))

    service = info.context["service"]
    user = info.context["request"].current_owner or info.context["request"].user

    if settings.IS_ENTERPRISE and settings.GUEST_ACCESS is False:
        if not user or not user.is_authenticated:
            raise UnauthorizedGuestAccess()

        # per product spec, if guestAccess is off for the environment, the current enterpriseUser
        # must be "activated" in the given target owner (e.g., "codecov" org) in order to see things
        target = await get_owner(service, username)
        if user.ownerid not in target.plan_activated_users:
            raise UnauthorizedGuestAccess()

    return await get_owner(service, username)


@query_bindable.field("config")
def resolve_config(_: Any, info: GraphQLResolveInfo) -> object:
    configure_sentry_scope(query_name(info))

    # we have to return something here just to allow access to the child resolvers
    return object()
