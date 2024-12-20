from typing import List, Optional

from ariadne import ObjectType
from shared.plan.constants import PlanData
from shared.plan.service import PlanService

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

plan_representation = ariadne_load_local_graphql(
    __file__, "plan_representation.graphql"
)
plan_representation_bindable = ObjectType("PlanRepresentation")


@plan_representation_bindable.field("marketingName")
def resolve_marketing_name(plan_data: PlanData, info) -> str:
    return plan_data["marketing_name"]


@plan_representation_bindable.field("planName")
def resolve_plan_name(plan_data: PlanData, info) -> str:
    return plan_data["value"]


@plan_representation_bindable.field("value")
def resolve_plan_value(plan_data: PlanData, info) -> str:
    return plan_data["value"]


@plan_representation_bindable.field("billingRate")
def resolve_billing_rate(plan_data: PlanData, info) -> Optional[str]:
    return plan_data["billing_rate"]


@plan_representation_bindable.field("baseUnitPrice")
def resolve_base_unit_price(plan_data: PlanData, info) -> int:
    return plan_data["base_unit_price"]


@plan_representation_bindable.field("benefits")
def resolve_benefits(plan_data: PlanData, info) -> List[str]:
    plan_service: PlanService = info.context["plan_service"]
    if plan_service.is_org_trialing:
        benefits_with_pretrial_users = list(
            map(
                lambda benefit: benefit.replace(
                    "Up to 1 user", f"Up to {plan_service.pretrial_users_count} users"
                ),
                plan_data["benefits"],
            )
        )
        return benefits_with_pretrial_users
    return plan_data["benefits"]


@plan_representation_bindable.field("monthlyUploadLimit")
def resolve_monthly_uploads_limit(plan_data: PlanData, info) -> Optional[int]:
    return plan_data["monthly_uploads_limit"]


@plan_representation_bindable.field("isEnterprisePlan")
def resolve_is_enterprise(plan_data: PlanData, info) -> bool:
    return plan_data["is_enterprise_plan"]


@plan_representation_bindable.field("isFreePlan")
def resolve_is_free(plan_data: PlanData, info) -> bool:
    return plan_data["is_free_plan"]


@plan_representation_bindable.field("isProPlan")
def resolve_is_pro(plan_data: PlanData, info) -> bool:
    return plan_data["is_pro_plan"]


@plan_representation_bindable.field("isTeamPlan")
def resolve_is_team(plan_data: PlanData, info) -> bool:
    return plan_data["is_team_plan"]


@plan_representation_bindable.field("isSentryPlan")
def resolve_is_sentry(plan_data: PlanData, info) -> bool:
    return plan_data["is_sentry_plan"]


@plan_representation_bindable.field("isTrialPlan")
def resolve_is_trial(plan_data: PlanData, info) -> bool:
    return plan_data["is_trial_plan"]
