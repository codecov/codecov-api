from ariadne import ObjectType
from codecov_auth.models import OktaSettings
from codecov.db import sync_to_async
from graphql_api.helpers.mutation import require_part_of_org

account_bindable = ObjectType("Account")


@account_bindable.field("name")
def resolve_name(account, info):
    return account.name


@account_bindable.field("oktaConfig")
@sync_to_async
def resolve_okta_config(account, info):
    return OktaSettings.objects.filter(account_id=account.pk).first()
