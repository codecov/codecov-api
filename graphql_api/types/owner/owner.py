from datetime import datetime
from hashlib import sha1
from typing import Iterable, List, Optional

import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case

import timeseries.helpers as timeseries_helpers
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import Owner
from core.models import Repository
from graphql_api.actions.repository import list_repository_for_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering
from services.profiling import ProfilingSummary
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval, MeasurementSummary

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
        queryset,
        ordering=(ordering, RepositoryOrdering.ID),
        ordering_direction=ordering_direction,
        **kwargs
    )


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


@owner_bindable.field("hashOwnerid")
def resolve_hash_ownerid(owner, info):
    hash_ownerid = sha1(str(owner.ownerid).encode())
    return hash_ownerid.hexdigest()


@owner_bindable.field("orgUploadToken")
def resolve_org_upload_token(owner, info, **kwargs):
    command = info.context["executor"].get_command("owner")
    return command.get_org_upload_token(owner)


@owner_bindable.field("defaultOrgUsername")
@sync_to_async
def resolve_org_default_org_username(owner: Owner, info, **kwargs) -> int:
    return None if owner.default_org is None else owner.default_org.username


@owner_bindable.field("measurements")
@sync_to_async
def resolve_measurements(
    owner: Owner,
    info,
    interval: Interval,
    after: datetime,
    before: datetime,
    repos: Optional[List[str]] = None,
) -> Iterable[MeasurementSummary]:
    user = info.context["request"].user

    queryset = Repository.objects.filter(author=owner).viewable_repos(user)
    if repos is None:
        repo_ids = queryset.values_list("pk", flat=True)
    else:
        repo_ids = queryset.filter(name__in=repos).values_list("pk", flat=True)

    return fill_sparse_measurements(
        timeseries_helpers.owner_coverage_measurements_with_fallback(
            owner,
            list(repo_ids),
            interval,
            after,
            before,
        ),
        interval,
        after,
        before,
    )
