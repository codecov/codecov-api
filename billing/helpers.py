from django.conf import settings
from django.db.models import QuerySet
from shared.django_apps.codecov_auth.models import BillingRate
from shared.django_apps.codecov_auth.tests.factories import PlanFactory, TierFactory
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName, PlanPrice, TierName

from codecov_auth.models import Owner, Plan


def on_enterprise_plan(owner: Owner) -> bool:
    plan = Plan.objects.select_related("tier").get(name=owner.plan)
    return settings.IS_ENTERPRISE or (plan.tier.tier_name == TierName.ENTERPRISE.value)


def get_all_admins_for_owners(owners: QuerySet[Owner]):
    admin_ids = set()
    for owner in owners:
        if owner.admins:
            admin_ids.update(owner.admins)

        # Add the owner's email as well - for user owners, admins is empty.
        if owner.email:
            admin_ids.add(owner.ownerid)

    admins: QuerySet[Owner] = Owner.objects.filter(pk__in=admin_ids)
    return admins


def mock_all_plans_and_tiers():
    TierFactory(tier_name=TierName.BASIC.value)

    trial_tier = TierFactory(tier_name=TierName.TRIAL.value)
    PlanFactory(
        tier=trial_tier,
        name=PlanName.TRIAL_PLAN_NAME.value,
        paid_plan=False,
        marketing_name="Developer",
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        stripe_id="plan_trial",
    )

    pro_tier = TierFactory(tier_name=TierName.PRO.value)
    PlanFactory(
        name=PlanName.CODECOV_PRO_MONTHLY.value,
        tier=pro_tier,
        marketing_name="Pro",
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        billing_rate=BillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        paid_plan=True,
        stripe_id="plan_pro",
    )
    PlanFactory(
        name=PlanName.CODECOV_PRO_YEARLY.value,
        tier=pro_tier,
        marketing_name="Pro",
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        billing_rate=BillingRate.ANNUALLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        paid_plan=True,
        stripe_id="plan_pro_yearly",
    )

    team_tier = TierFactory(tier_name=TierName.TEAM.value)
    PlanFactory(
        name=PlanName.TEAM_MONTHLY.value,
        tier=team_tier,
        marketing_name="Team",
        benefits=[
            "Up to 10 users",
            "Unlimited repositories",
            "2500 private repo uploads",
            "Patch coverage analysis",
        ],
        billing_rate=BillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.TEAM_MONTHLY.value,
        monthly_uploads_limit=2500,
        paid_plan=True,
        stripe_id="plan_team_monthly",
    )
    PlanFactory(
        name=PlanName.TEAM_YEARLY.value,
        tier=team_tier,
        marketing_name="Team",
        benefits=[
            "Up to 10 users",
            "Unlimited repositories",
            "2500 private repo uploads",
            "Patch coverage analysis",
        ],
        billing_rate=BillingRate.ANNUALLY.value,
        base_unit_price=PlanPrice.TEAM_YEARLY.value,
        monthly_uploads_limit=2500,
        paid_plan=True,
        stripe_id="plan_team_yearly",
    )

    sentry_tier = TierFactory(tier_name=TierName.SENTRY.value)
    PlanFactory(
        name=PlanName.SENTRY_MONTHLY.value,
        tier=sentry_tier,
        marketing_name="Sentry Pro",
        billing_rate=BillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        paid_plan=True,
        benefits=[
            "Includes 5 seats",
            "$12 per additional seat",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        stripe_id="plan_sentry_monthly",
    )
    PlanFactory(
        name=PlanName.SENTRY_YEARLY.value,
        tier=sentry_tier,
        marketing_name="Sentry Pro",
        billing_rate=BillingRate.ANNUALLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        paid_plan=True,
        benefits=[
            "Includes 5 seats",
            "$10 per additional seat",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        stripe_id="plan_sentry_yearly",
    )

    enterprise_tier = TierFactory(tier_name=TierName.ENTERPRISE.value)
    PlanFactory(
        name=PlanName.ENTERPRISE_CLOUD_MONTHLY.value,
        tier=enterprise_tier,
        marketing_name="Enterprise Cloud",
        billing_rate=BillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        paid_plan=True,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        stripe_id="plan_enterprise_cloud_monthly",
    )
    PlanFactory(
        name=PlanName.ENTERPRISE_CLOUD_YEARLY.value,
        tier=enterprise_tier,
        marketing_name="Enterprise Cloud",
        billing_rate=BillingRate.ANNUALLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        paid_plan=True,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        stripe_id="plan_enterprise_cloud_yearly",
    )

    PlanFactory(
        name=DEFAULT_FREE_PLAN,
        tier=team_tier,
        marketing_name="Developer",
        billing_rate=None,
        base_unit_price=0,
        paid_plan=False,
        monthly_uploads_limit=250,
        benefits=[
            "Up to 1 user",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
        stripe_id="plan_default_free",
    )
