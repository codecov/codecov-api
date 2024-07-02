from ariadne import ObjectType

from codecov_auth.models import OktaSettings

okta_config_bindable = ObjectType("OktaConfig")


@okta_config_bindable.field("clientId")
def resolve_client_id(okta_config: OktaSettings, info) -> str:
    return okta_config.client_id


@okta_config_bindable.field("clientSecret")
def resolve_client_secret(okta_config: OktaSettings, info) -> str:
    return okta_config.client_secret


@okta_config_bindable.field("url")
def resolve_url(okta_config: OktaSettings, info) -> str:
    return okta_config.url


@okta_config_bindable.field("enabled")
def resolve_enabled(okta_config: OktaSettings, info) -> bool:
    return okta_config.enabled


@okta_config_bindable.field("enforced")
def resolve_enforced(okta_config: OktaSettings, info) -> bool:
    return okta_config.enforced
