from typing import Iterable

import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case
from django.conf import settings

from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner
from graphql_api.actions.measurement import measurement_queryset
from graphql_api.actions.repository import list_repository_for_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering
from services.profiling import ProfilingSummary
from timeseries.models import Interval

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner = owner + build_connection_graphql("RepositoryConnection", "Repository")
owner_bindable = ObjectType("Owner")


@owner_bindable.field("repositories")
@convert_kwargs_to_snake_case
def resolve_repositories(
    owner,
    info,
    filters=None,
    ordering=RepositoryOrdering.ID,
    ordering_direction=OrderingDirection.ASC,
    **kwargs
):
    current_user = info.context["request"].user
    queryset = list_repository_for_owner(current_user, owner, filters)
    return queryset_to_connection(
        queryset, ordering=(ordering,), ordering_direction=ordering_direction, **kwargs
    )


@owner_bindable.field("measurements")
@convert_kwargs_to_snake_case
def resolve_measurements(
    owner: Owner, info, name: str, interval: Interval, filters: Iterable
):
    if not settings.TIMESERIES_ENABLED:
        return [[] for filter in filters]

    current_user = info.context["request"].user
    return measurement_queryset(current_user, owner, name, interval, filters)


@owner_bindable.field("isCurrentUserPartOfOrg")
def resolve_is_current_user_part_of_org(owner, info):
    current_user = info.context["request"].user
    return current_user_part_of_org(current_user, owner)


@owner_bindable.field("yaml")
def resolve_yaml(owner, info):
    current_user = info.context["request"].user
    if owner.yaml is None:
        return
    if not current_user_part_of_org(current_user, owner):
        return
    return yaml.dump(owner.yaml)


@owner_bindable.field("repository")
async def resolve_repository(owner, info, name):
    command = info.context["executor"].get_command("repository")
    repository = await command.fetch_repository(owner, name)

    info.context["profiling_summary"] = ProfilingSummary(repository)

    return repository


@owner_bindable.field("numberOfUploads")
async def resolve_number_of_uploads(owner, info, **kwargs):
    command = info.context["executor"].get_command("owner")
    return await command.get_uploads_number_per_user(owner)


@owner_bindable.field("isAdmin")
def resolve_is_current_user_an_admin(owner, info):
    current_user = info.context["request"].user
    command = info.context["executor"].get_command("owner")
    return command.get_is_current_user_an_admin(owner, current_user)
