from ariadne import ObjectType
from codecov_auth.models import OktaSettings

account_bindable = ObjectType("Account")

@account_bindable.field("oktaConfig")
def resolve_okta_config(account, info):
    return OktaSettings.objects.filter(account_id=account.pk).first()