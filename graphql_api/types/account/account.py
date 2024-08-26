from ariadne import ObjectType

from codecov.db import sync_to_async
from codecov_auth.models import Account, OktaSettings

account_bindable = ObjectType("Account")


@account_bindable.field("name")
def resolve_name(account: Account, info) -> str:
    return account.name


@account_bindable.field("oktaConfig")
@sync_to_async
def resolve_okta_config(account: Account, info) -> OktaSettings:
    return OktaSettings.objects.filter(account_id=account.pk).first()
