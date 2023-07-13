from datetime import datetime
from typing import List, Optional

from ariadne import ObjectType, convert_kwargs_to_snake_case

from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from services.plan import (
    MonthlyUploadLimits,
    PlanBillingRate,
    PlanMarketingName,
    PlanNames,
    PlanPrice,
    PlanService,
    TrialDaysAmount,
    TrialStatus,
)

plan = ariadne_load_local_graphql(__file__, "plan.graphql")
plan_bindable = ObjectType("Plan")


@plan_bindable.field("trialStartDate")
@convert_kwargs_to_snake_case
def resolve_trial_start_date(plan_service: PlanService, info) -> Optional[datetime]:
    return plan_service.trial_start_date


@plan_bindable.field("trialEndDate")
@convert_kwargs_to_snake_case
def resolve_trial_end_date(plan_service: PlanService, info) -> Optional[datetime]:
    return plan_service.trial_end_date


@plan_bindable.field("trialStatus")
@convert_kwargs_to_snake_case
def resolve_trial_status(plan_service: PlanService, info) -> TrialStatus:
    return plan_service.trial_status


@plan_bindable.field("marketingName")
@convert_kwargs_to_snake_case
def resolve_marketing_name(plan_service: PlanService, info) -> PlanMarketingName:
    return plan_service.marketing_name


@plan_bindable.field("planName")
@convert_kwargs_to_snake_case
def resolve_plan_name(plan_service: PlanService, info) -> PlanNames:
    return plan_service.plan_name


@plan_bindable.field("billingRate")
@convert_kwargs_to_snake_case
def resolve_billing_rate(plan_service: PlanService, info) -> Optional[PlanBillingRate]:
    return plan_service.billing_rate


@plan_bindable.field("baseUnitPrice")
@convert_kwargs_to_snake_case
def resolve_base_unit_price(plan_service: PlanService, info) -> PlanPrice:
    return plan_service.base_unit_price


@plan_bindable.field("benefits")
@convert_kwargs_to_snake_case
def resolve_benefits(plan_service: PlanService, info) -> List[str]:
    return plan_service.benefits


@plan_bindable.field("monthlyUploadLimit")
@convert_kwargs_to_snake_case
def resolve_monthly_uploads_limit(
    plan_service: PlanService, info
) -> Optional[MonthlyUploadLimits]:
    return plan_service.monthly_uploads_limit
