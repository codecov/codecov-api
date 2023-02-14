from ariadne import ObjectType, convert_kwargs_to_snake_case

from codecov.db import sync_to_async
from codecov_auth.models import Owner, OwnerProfile
from graphql_api.actions.owner import (
    get_owner_login_sessions,
    get_user_tokens,
    search_my_owners,
)
from graphql_api.actions.repository import search_repos
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering

me = ariadne_load_local_graphql(__file__, "me.graphql")
me = me + build_connection_graphql("ViewableRepositoryConnection", "Repository")
me = me + build_connection_graphql("MyOrganizationConnection", "Owner")
me = me + build_connection_graphql("SessionConnection", "Session")
me = me + build_connection_graphql("UserTokenConnection", "UserToken")
me_bindable = ObjectType("Me")


@me_bindable.field("user")
def resolve_user(user, _):
    return user


@me_bindable.field("owner")
def resolve_owner(user, _):
    """
    Current user is also an owner in which we can fetch repositories
    """
    return user


@me_bindable.field("viewableRepositories")
@convert_kwargs_to_snake_case
def resolve_viewable_repositories(
    current_user,
    _,
    filters=None,
    ordering=RepositoryOrdering.ID,
    ordering_direction=OrderingDirection.ASC,
    **kwargs,
):
    queryset = search_repos(current_user, filters)
    return queryset_to_connection(
        queryset,
        ordering=(ordering, RepositoryOrdering.ID),
        ordering_direction=ordering_direction,
        **kwargs,
    )


@me_bindable.field("myOrganizations")
def resolve_my_organizations(current_user, _, filters=None, **kwargs):
    queryset = search_my_owners(current_user, filters)
    return queryset_to_connection(
        queryset,
        ordering=("ownerid",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@me_bindable.field("sessions")
def resolve_sessions(current_user, _, **kwargs):
    queryset = get_owner_login_sessions(current_user)
    return queryset_to_connection(
        queryset,
        ordering=("sessionid",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@me_bindable.field("tokens")
def resolve_tokens(current_user, _, **kwargs):
    queryset = get_user_tokens(current_user)
    return queryset_to_connection(
        queryset,
        ordering=("created_at",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@me_bindable.field("isSyncingWithGitProvider")
def resolve_is_syncing_with_git_provider(_, info):
    command = info.context["executor"].get_command("owner")
    return command.is_syncing()


@me_bindable.field("trackingMetadata")
def resolve_tracking_data(current_user, _, **kwargs):
    return current_user


tracking_metadata_bindable = ObjectType("trackingMetadata")


@tracking_metadata_bindable.field("profile")
@sync_to_async
def resolve_profile(owner: Owner, info) -> OwnerProfile:
    try:
        return owner.profile
    except OwnerProfile.DoesNotExist:
        return None
