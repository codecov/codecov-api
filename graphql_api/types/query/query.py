from typing import Optional

from ariadne import ObjectType
from django.conf import settings
from graphql import GraphQLError, GraphQLResolveInfo
from sentry_sdk import configure_scope

from codecov.commands.exceptions import UnauthorizedGuestAccess
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from graphql_api.actions.owner import get_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from utils.services import get_long_service_name

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")


def query_name(info: GraphQLResolveInfo) -> Optional[str]:
    if info.operation and info.operation.name:
        return info.operation.name.value


def configure_sentry_scope(query_name: str):
    # this sets the Sentry transaction name to the GraphQL query name which
    # should make it easier to search/filter transactions
    # we're configuring this here since it's the main entrypoint into GraphQL resolvers

    # https://docs.sentry.io/platforms/python/enriching-events/transaction-name/
    with configure_scope() as scope:
        if scope.transaction:
            scope.transaction.name = f"GraphQL [{query_name}]"


@query_bindable.field("me")
@sync_to_async
def resolve_me(_, info) -> Optional[Owner]:
    configure_sentry_scope(query_name(info))
    # will be `None` for anonymous users or users w/ no linked owners
    return info.context["request"].current_owner


@query_bindable.field("owner")
def resolve_owner(_, info, username):
    configure_sentry_scope(query_name(info))

    service = info.context["service"]
    user = info.context["request"].current_owner

    if settings.IS_ENTERPRISE and settings.GUEST_ACCESS is False:
        if not user or not user.is_authenticated:
            raise UnauthorizedGuestAccess()

    return get_owner(service, username)


@query_bindable.field("config")
def resolve_config(_, info):
    configure_sentry_scope(query_name(info))

    # we have to return something here just to allow access to the child resolvers
    return object()
