import json
import yaml
from ariadne import convert_kwargs_to_snake_case, ObjectType

from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.actions.owner import current_user_part_of_org
from graphql_api.actions.repository import list_repository_for_owner
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering


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
        queryset, ordering=ordering, ordering_direction=ordering_direction, **kwargs
    )


@owner_bindable.field("isCurrentUserPartOfOrg")
def resolve_is_current_user_part_of_org(owner, info):
    current_user = info.context["request"].user
    return current_user_part_of_org(current_user, owner)


@owner_bindable.field("yaml")
def resolve_yaml(owner, info):
    return yaml.dump(owner.yaml)
