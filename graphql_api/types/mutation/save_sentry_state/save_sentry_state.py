from ariadne import UnionType

import services.sentry as sentry
from codecov.commands.exceptions import Unauthenticated, ValidationError
from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_save_sentry_state(_, info, input):
    current_user = info.context["request"].user
    if not current_user.is_authenticated:
        raise Unauthenticated()

    try:
        sentry.save_sentry_state(current_user, input.get("state"))
    except sentry.SentryInvalidStateError:
        raise ValidationError("Invalid state")
    except sentry.SentryUserAlreadyExistsError:
        raise ValidationError("Invalid Sentry user")


error_save_sentry_state = UnionType("SaveSentryStateError")
error_save_sentry_state.type_resolver(resolve_union_error_type)
