from datetime import datetime
from hashlib import sha1
from typing import Iterable, List, Optional

import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case

import services.activation as activation
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
from graphql_api.helpers.mutation import require_part_of_org
from graphql_api.types.enums import OrderingDirection, RepositoryOrdering
from graphql_api.types.errors.errors import NotFoundError, OwnerNotActivatedError
from plan.constants import FREE_PLAN_REPRESENTATIONS, PlanData, PlanName
from plan.service import PlanService
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
    **kwargs,
):
    current_owner = info.context["request"].current_owner
    queryset = list_repository_for_owner(current_owner, owner, filters)
    return queryset_to_connection(
        queryset,
        ordering=(ordering, RepositoryOrdering.ID),
        ordering_direction=ordering_direction,
        **kwargs,
    )


@owner_bindable.field("isCurrentUserPartOfOrg")
@sync_to_async
def resolve_is_current_user_part_of_org(owner, info):
    current_owner = info.context["request"].current_owner
    return current_user_part_of_org(current_owner, owner)


@owner_bindable.field("yaml")
def resolve_yaml(owner, info):
    if owner.yaml is None:
        return
    current_owner = info.context["request"].current_owner
    if not current_user_part_of_org(current_owner, owner):
        return
    return yaml.dump(owner.yaml)


@owner_bindable.field("plan")
@require_part_of_org
def resolve_plan(owner: Owner, info) -> PlanService:
    return PlanService(current_org=owner)


@owner_bindable.field("pretrialPlan")
@convert_kwargs_to_snake_case
@require_part_of_org
def resolve_plan_representation(owner: Owner, info) -> PlanData:
    info.context["plan_service"] = PlanService(current_org=owner)
    return FREE_PLAN_REPRESENTATIONS[PlanName.BASIC_PLAN_NAME.value]


@owner_bindable.field("availablePlans")
@convert_kwargs_to_snake_case
@require_part_of_org
def resolve_available_plans(owner: Owner, info) -> List[PlanData]:
    plan_service = PlanService(current_org=owner)
    info.context["plan_service"] = plan_service
    owner = info.context["request"].current_owner
    return plan_service.available_plans(owner=owner)


@owner_bindable.field("hasPrivateRepos")
@sync_to_async
@require_part_of_org
def resolve_has_private_repos(owner: Owner, info) -> List[PlanData]:
    return owner.has_private_repos


@owner_bindable.field("ownerid")
@require_part_of_org
def resolve_ownerid(owner, info) -> int:
    return owner.ownerid


@owner_bindable.field("repository")
async def resolve_repository(owner, info, name):
    command = info.context["executor"].get_command("repository")
    repository: Optional[Repository] = await command.fetch_repository(owner, name)

    if repository is None:
        return NotFoundError()

    current_owner = info.context["request"].current_owner
    has_products_enabled = (
        repository.bundle_analysis_enabled and repository.coverage_enabled
    )

    if repository.private and has_products_enabled:
        await sync_to_async(activation.try_auto_activate)(owner, current_owner)
        is_owner_activated = await sync_to_async(activation.is_activated)(
            owner, current_owner
        )
        if not is_owner_activated:
            return OwnerNotActivatedError()

    info.context["profiling_summary"] = ProfilingSummary(repository)
    return repository


@owner_bindable.field("repositoryDeprecated")
async def resolve_repository_deprecated(owner, info, name):
    command = info.context["executor"].get_command("repository")
    repository: Optional[Repository] = await command.fetch_repository(owner, name)

    if repository is not None:
        current_owner = info.context["request"].current_owner
        if repository.private:
            await sync_to_async(activation.try_auto_activate)(owner, current_owner)

        info.context["profiling_summary"] = ProfilingSummary(repository)

    return repository


@owner_bindable.field("numberOfUploads")
@require_part_of_org
async def resolve_number_of_uploads(owner, info, **kwargs):
    command = info.context["executor"].get_command("owner")
    return await command.get_uploads_number_per_user(owner)


@owner_bindable.field("isAdmin")
@require_part_of_org
def resolve_is_current_user_an_admin(owner, info):
    current_owner = info.context["request"].current_owner
    command = info.context["executor"].get_command("owner")
    return command.get_is_current_user_an_admin(owner, current_owner)


@owner_bindable.field("hashOwnerid")
@require_part_of_org
def resolve_hash_ownerid(owner, info):
    hash_ownerid = sha1(str(owner.ownerid).encode())
    return hash_ownerid.hexdigest()


@owner_bindable.field("orgUploadToken")
@require_part_of_org
def resolve_org_upload_token(owner, info, **kwargs):
    command = info.context["executor"].get_command("owner")
    return command.get_org_upload_token(owner)


@owner_bindable.field("defaultOrgUsername")
@sync_to_async
@require_part_of_org
def resolve_org_default_org_username(owner: Owner, info, **kwargs) -> int:
    return None if owner.default_org is None else owner.default_org.username


@owner_bindable.field("measurements")
@sync_to_async
@convert_kwargs_to_snake_case
def resolve_measurements(
    owner: Owner,
    info,
    interval: Interval,
    after: Optional[datetime] = None,
    before: Optional[datetime] = None,
    repos: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
) -> Iterable[MeasurementSummary]:
    current_owner = info.context["request"].current_owner

    queryset = Repository.objects.filter(author=owner).viewable_repos(current_owner)

    if is_public is not None:
        queryset = queryset.filter(private=not is_public)

    if repos is None:
        repo_ids = queryset.values_list("pk", flat=True)
    else:
        repo_ids = queryset.filter(name__in=repos).values_list("pk", flat=True)

    return fill_sparse_measurements(
        timeseries_helpers.owner_coverage_measurements_with_fallback(
            owner,
            list(repo_ids),
            interval,
            start_date=after,
            end_date=before,
        ),
        interval,
        start_date=after,
        end_date=before,
    )


@owner_bindable.field("isCurrentUserActivated")
@sync_to_async
def resolve_is_current_user_activated(owner, info):
    current_user = info.context["request"].user
    if not current_user.is_authenticated:
        return False

    current_owner = info.context["request"].current_owner
    if not current_owner:
        return False

    if owner.ownerid == current_owner.ownerid or owner.is_admin(current_owner):
        return True
    if owner.plan_activated_users is None:
        return False

    return (
        bool(owner.plan_activated_users)
        and current_owner.ownerid in owner.plan_activated_users
    )
