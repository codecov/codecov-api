from ariadne import UnionType

import services.sentry as sentry
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
@sync_to_async
def resolve_save_sentry_state(_, info, input):
    current_owner = info.context["request"].current_owner
    try:
        sentry.save_sentry_state(current_owner, input.get("state"))
    except sentry.SentryInvalidStateError:
        raise ValidationError("Invalid state")
    except sentry.SentryUserAlreadyExistsError:
        raise ValidationError("Invalid Sentry user")


error_save_sentry_state = UnionType("SaveSentryStateError")
error_save_sentry_state.type_resolver(resolve_union_error_type)
