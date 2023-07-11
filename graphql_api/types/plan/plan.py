from datetime import datetime
from typing import Optional

from ariadne import ObjectType, convert_kwargs_to_snake_case

from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from services.plan import PlanService, TrialStatus

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
