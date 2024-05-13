from typing import Optional

from ariadne import ObjectType
from django.conf import settings
from graphql.type.definition import GraphQLResolveInfo

import services.self_hosted as self_hosted

self_hosted_settings_bindable = ObjectType("SelfHostedSettings")


@self_hosted_settings_bindable.field("planAutoActivate")
def resolve_plan_auto_activate(_, info: GraphQLResolveInfo) -> Optional[bool]:
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.is_autoactivation_enabled()


@self_hosted_settings_bindable.field("seatsLimit")
def resolve_expiration_date(_, info: GraphQLResolveInfo) -> Optional[int]:
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.activated_owners().count()


@self_hosted_settings_bindable.field("seatsUsed")
def resolve_seats_used(_, info: GraphQLResolveInfo) -> Optional[int]:
    if not settings.IS_ENTERPRISE:
        return None

    return self_hosted.license_seats()
