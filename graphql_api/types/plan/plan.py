from datetime import datetime
from typing import List, Optional

from ariadne import ObjectType
from shared.plan.constants import PlanBillingRate, TrialStatus
from shared.plan.service import PlanService

from codecov.db import sync_to_async
from graphql_api.helpers.ariadne import ariadne_load_local_graphql

plan = ariadne_load_local_graphql(__file__, "plan.graphql")
plan_bindable = ObjectType("Plan")


@plan_bindable.field("trialStartDate")
def resolve_trial_start_date(plan_service: PlanService, info) -> Optional[datetime]:
    return plan_service.trial_start_date


@plan_bindable.field("trialTotalDays")
@sync_to_async
def resolve_trial_total_days(plan_service: PlanService, info) -> Optional[int]:
    return plan_service.trial_total_days


@plan_bindable.field("trialEndDate")
def resolve_trial_end_date(plan_service: PlanService, info) -> Optional[datetime]:
    return plan_service.trial_end_date


@plan_bindable.field("trialStatus")
def resolve_trial_status(plan_service: PlanService, info) -> TrialStatus:
    if not plan_service.trial_status:
        return TrialStatus.NOT_STARTED
    return TrialStatus(plan_service.trial_status)


@plan_bindable.field("marketingName")
@sync_to_async
def resolve_marketing_name(plan_service: PlanService, info) -> str:
    return plan_service.marketing_name


@plan_bindable.field("value")
@sync_to_async
def resolve_plan_name_as_value(plan_service: PlanService, info) -> str:
    return plan_service.plan_name


@plan_bindable.field("tierName")
@sync_to_async
def resolve_tier_name(plan_service: PlanService, info) -> str:
    return plan_service.tier_name


@plan_bindable.field("billingRate")
@sync_to_async
def resolve_billing_rate(plan_service: PlanService, info) -> Optional[PlanBillingRate]:
    return plan_service.billing_rate


@plan_bindable.field("baseUnitPrice")
@sync_to_async
def resolve_base_unit_price(plan_service: PlanService, info) -> int:
    return plan_service.base_unit_price


@plan_bindable.field("benefits")
@sync_to_async
def resolve_benefits(plan_service: PlanService, info) -> List[str]:
    return plan_service.benefits


@plan_bindable.field("pretrialUsersCount")
@sync_to_async
def resolve_pretrial_users_count(plan_service: PlanService, info) -> Optional[int]:
    if plan_service.is_org_trialing:
        return plan_service.pretrial_users_count
    return None


@plan_bindable.field("monthlyUploadLimit")
@sync_to_async
def resolve_monthly_uploads_limit(plan_service: PlanService, info) -> Optional[int]:
    return plan_service.monthly_uploads_limit


@plan_bindable.field("planUserCount")
@sync_to_async
def resolve_plan_user_count(plan_service: PlanService, info) -> int:
    return plan_service.plan_user_count


@plan_bindable.field("hasSeatsLeft")
@sync_to_async
def resolve_has_seats_left(plan_service: PlanService, info) -> bool:
    return plan_service.has_seats_left


@plan_bindable.field("isEnterprisePlan")
@sync_to_async
def resolve_is_enterprise_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_enterprise_plan


@plan_bindable.field("isFreePlan")
@sync_to_async
def resolve_is_free_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_free_plan


@plan_bindable.field("isProPlan")
@sync_to_async
def resolve_is_pro_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_pro_plan


@plan_bindable.field("isSentryPlan")
@sync_to_async
def resolve_is_sentry_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_sentry_plan


@plan_bindable.field("isTeamPlan")
@sync_to_async
def resolve_is_team_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_team_plan


@plan_bindable.field("isTrialPlan")
@sync_to_async
def resolve_is_trial_plan(plan_service: PlanService, info) -> bool:
    return plan_service.is_trial_plan
