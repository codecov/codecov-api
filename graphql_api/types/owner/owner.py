from datetime import datetime
from hashlib import sha1
from typing import Iterable, List, Optional

import shared.rate_limits as rate_limits
import stripe
import yaml
from ariadne import ObjectType, convert_kwargs_to_snake_case

import services.activation as activation
import timeseries.helpers as timeseries_helpers
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import (
    SERVICE_GITHUB,
    SERVICE_GITHUB_ENTERPRISE,
    Account,
    Owner,
)
from codecov_auth.views.okta_cloud import OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY
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
from services.billing import BillingService
from services.profiling import ProfilingSummary
from services.redis_configuration import get_redis_connection
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval, MeasurementSummary

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner = owner + build_connection_graphql("RepositoryConnection", "Repository")
owner_bindable = ObjectType("Owner")


@owner_bindable.field("repositories")
@convert_kwargs_to_snake_case
def resolve_repositories(
    owner: Owner,
    info,
    filters=None,
    ordering=RepositoryOrdering.ID,
    ordering_direction=OrderingDirection.ASC,
    **kwargs,
):
    current_owner = info.context["request"].current_owner
    okta_account_auths: list[int] = info.context["request"].session.get(
        OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY, []
    )
    queryset = list_repository_for_owner(
        current_owner, owner, filters, okta_account_auths
    )
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
def resolve_yaml(owner: Owner, info):
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
def resolve_ownerid(owner: Owner, info) -> int:
    return owner.ownerid


@owner_bindable.field("repository")
async def resolve_repository(owner: Owner, info, name):
    command = info.context["executor"].get_command("repository")
    okta_authenticated_accounts: list[int] = info.context["request"].session.get(
        OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY, []
    )
    repository: Optional[Repository] = await command.fetch_repository(
        owner, name, okta_authenticated_accounts
    )

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


@owner_bindable.field("numberOfUploads")
@require_part_of_org
async def resolve_number_of_uploads(owner: Owner, info, **kwargs):
    command = info.context["executor"].get_command("owner")
    return await command.get_uploads_number_per_user(owner)


@owner_bindable.field("isAdmin")
@require_part_of_org
def resolve_is_current_user_an_admin(owner: Owner, info):
    current_owner = info.context["request"].current_owner
    command = info.context["executor"].get_command("owner")
    return command.get_is_current_user_an_admin(owner, current_owner)


@owner_bindable.field("hashOwnerid")
@require_part_of_org
def resolve_hash_ownerid(owner: Owner, info):
    hash_ownerid = sha1(str(owner.ownerid).encode())
    return hash_ownerid.hexdigest()


@owner_bindable.field("orgUploadToken")
@require_part_of_org
def resolve_org_upload_token(owner: Owner, info, **kwargs):
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

    okta_authenticated_accounts: list[int] = info.context["request"].session.get(
        OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY, []
    )

    queryset = (
        Repository.objects.filter(author=owner)
        .viewable_repos(current_owner)
        .exclude_accounts_enforced_okta(okta_authenticated_accounts)
    )

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
def resolve_is_current_user_activated(owner: Owner, info):
    current_user = info.context["request"].user
    if not current_user.is_authenticated:
        return False

    current_owner = info.context["request"].current_owner
    if not current_owner:
        return False

    if owner.ownerid == current_owner.ownerid:
        return True
    if owner.plan_activated_users is None:
        return False

    return (
        bool(owner.plan_activated_users)
        and current_owner.ownerid in owner.plan_activated_users
    )


@owner_bindable.field("invoices")
@require_part_of_org
def resolve_owner_invoices(owner: Owner, info) -> list | None:
    return BillingService(requesting_user=owner).list_filtered_invoices(owner, 100)


@owner_bindable.field("isGithubRateLimited")
@sync_to_async
def resolve_is_github_rate_limited(owner: Owner, info) -> bool | None:
    if owner.service != SERVICE_GITHUB and owner.service != SERVICE_GITHUB_ENTERPRISE:
        return False
    redis_connection = get_redis_connection()
    rate_limit_redis_key = rate_limits.determine_entity_redis_key(
        owner=owner, repository=None
    )
    return rate_limits.determine_if_entity_is_rate_limited(
        redis_connection, rate_limit_redis_key
    )


@owner_bindable.field("invoice")
@require_part_of_org
@convert_kwargs_to_snake_case
def resolve_owner_invoice(
    owner: Owner,
    info,
    invoice_id: str,
) -> stripe.Invoice | None:
    return BillingService(requesting_user=owner).get_invoice(owner, invoice_id)


@owner_bindable.field("account")
@require_part_of_org
@sync_to_async
def resolve_owner_account(owner: Owner, info) -> dict:
    account_id = owner.account_id
    return Account.objects.filter(pk=account_id).first()


@owner_bindable.field("isUserOktaAuthenticated")
@sync_to_async
@require_part_of_org
def resolve_is_user_okta_authenticated(owner: Owner, info) -> bool:
    okta_signed_in_accounts = info.context["request"].session.get(
        OKTA_SIGNED_IN_ACCOUNTS_SESSION_KEY,
        [],
    )
    if owner.account_id:
        return owner.account_id in okta_signed_in_accounts
    return False


@owner_bindable.field("delinquent")
@require_part_of_org
def resolve_delinquent(owner: Owner, info) -> bool | None:
    return owner.delinquent
