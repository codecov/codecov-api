from typing import Any, Dict

from ariadne import UnionType
from ariadne.types import GraphQLResolveInfo

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_create_stripe_setup_intent(
    _: Any, info: GraphQLResolveInfo, input: Dict[str, str]
) -> Dict[str, str]:
    command = info.context["executor"].get_command("owner")
    resp = await command.create_stripe_setup_intent(input.get("owner"))
    return {
        "client_secret": resp["client_secret"],
    }


error_create_stripe_setup_intent = UnionType("CreateStripeSetupIntentError")
error_create_stripe_setup_intent.type_resolver(resolve_union_error_type)
