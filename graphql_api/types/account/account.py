from ariadne import ObjectType

from codecov.db import sync_to_async
from codecov_auth.models import Account, OktaSettings

account_bindable = ObjectType("Account")


@account_bindable.field("name")
def resolve_name(account: Account, info) -> str:
    return account.name


@account_bindable.field("oktaConfig")
@sync_to_async
def resolve_okta_config(account: Account, info) -> OktaSettings | None:
    return OktaSettings.objects.filter(account_id=account.pk).first()

@account_bindable.field("totalSeatCount")
def resolve_total_seat_count(account: Account, info) -> int:
    return account.plan_seat_count + account.free_seat_count
