from typing import Any, Coroutine, Optional

from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from codecov.db import sync_to_async
from codecov_auth.models import Account, OktaSettings, Owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.types.enums.enums import OrderingDirection

account = ariadne_load_local_graphql(__file__, "account.graphql")
account = account + build_connection_graphql("AccountOrganizationConnection", "Owner")
account_bindable = ObjectType("Account")


@account_bindable.field("name")
def resolve_name(account: Account, info: GraphQLResolveInfo) -> str:
    return account.name


@account_bindable.field("oktaConfig")
@sync_to_async
def resolve_okta_config(
    account: Account, info: GraphQLResolveInfo
) -> OktaSettings | None:
    return OktaSettings.objects.filter(account_id=account.pk).first()


@account_bindable.field("totalSeatCount")
def resolve_total_seat_count(account: Account, info: GraphQLResolveInfo) -> int:
    return account.total_seat_count


@account_bindable.field("activatedUserCount")
@sync_to_async
def resolve_activated_user_count(account: Account, info: GraphQLResolveInfo) -> int:
    return account.activated_user_count


@account_bindable.field("organizations")
def resolve_organizations(
    account: Account,
    info: GraphQLResolveInfo,
    ordering_direction: Optional[OrderingDirection] = OrderingDirection.ASC,
    **kwargs: Any,
) -> Coroutine[Any, Any, Owner]:
    return queryset_to_connection(
        account.organizations,
        ordering=("username",),
        ordering_direction=ordering_direction,
        **kwargs,
    )
