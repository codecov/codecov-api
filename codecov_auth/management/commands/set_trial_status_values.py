from datetime import UTC, datetime

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from codecov_auth.models import Owner
from plan.constants import (
    FREE_PLAN_REPRESENTATIONS,
    PLANS_THAT_CAN_TRIAL,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    PlanName,
    TrialStatus,
)


class Command(BaseCommand):
    help = "Sets the initial trial status values for an owner"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("trial_status_type", type=str)

    def handle(self, *args, **options) -> None:
        trial_status_type = options.get("trial_status_type", {})

        # NOT_STARTED
        if trial_status_type == "all" or trial_status_type == "not_started":
            # Free plan customers
            Owner.objects.filter(
                plan__in=FREE_PLAN_REPRESENTATIONS,
                stripe_customer_id=None,
            ).update(trial_status=TrialStatus.NOT_STARTED.value)

        # ONGOING
        if trial_status_type == "all" or trial_status_type == "ongoing":
            Owner.objects.filter(
                plan__in=SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
                trial_end_date__gt=datetime.now(),
            ).update(trial_status=TrialStatus.ONGOING.value)

        # EXPIRED
        if trial_status_type == "all" or trial_status_type == "expired":
            Owner.objects.filter(
                # Currently paying sentry customer with trial_end_date
                Q(
                    plan__in=SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
                    stripe_customer_id__isnull=False,
                    stripe_subscription_id__isnull=False,
                    trial_end_date__lte=datetime.now(),
                )
                # Currently paying sentry customer without trial_end_date
                | Q(
                    plan__in=SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
                    stripe_customer_id__isnull=False,
                    stripe_subscription_id__isnull=False,
                    trial_start_date__isnull=True,
                    trial_end_date__isnull=True,
                )
                # Previously paid but now back to basic with trial start/end dates
                | Q(
                    plan=PlanName.BASIC_PLAN_NAME.value,
                    stripe_customer_id__isnull=False,
                    trial_start_date__isnull=False,
                    trial_end_date__isnull=False,
                )
            ).update(trial_status=TrialStatus.EXPIRED.value)

        # CANNOT_TRIAL
        if trial_status_type == "all" or trial_status_type == "cannot_trial":
            Owner.objects.filter(
                # Plans that cannot trial
                ~Q(plan__in=PLANS_THAT_CAN_TRIAL)
                # Previously paid but now back to basic without trial start/end dates
                | Q(
                    plan=PlanName.BASIC_PLAN_NAME.value,
                    stripe_customer_id__isnull=False,
                    trial_start_date__isnull=True,
                    trial_end_date__isnull=True,
                )
                # Currently paying customer that isn't a sentry plan (they would be expired)
                | Q(
                    ~Q(plan__in=SENTRY_PAID_USER_PLAN_REPRESENTATIONS),
                    stripe_subscription_id__isnull=False,
                    stripe_customer_id__isnull=False,
                )
                # Invoiced customers without stripe info
                | Q(
                    Q(plan__in=PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS),
                    stripe_subscription_id__isnull=True,
                    stripe_customer_id__isnull=True,
                )
            ).update(trial_status=TrialStatus.CANNOT_TRIAL.value)

        # DELETE ALL - in case something gets messed up
        if trial_status_type == "null_all_are_you_sure":
            Owner.objects.all().update(trial_status=None)


# Scenarios
# basic plan, without billing_info > not_started

# sentry plan, billing_info, with end date after today > ongoing

# sentry plan, billing_info, with end date before today > expired
# sentry plan, billing_info, subscription id > expired
# basic plan, with billing_info, with start/end dates > expired

# unsupported trial plan > cannot_trial
# supported paid plan, no end date > cannot_trial
# basic plan, with billing_info, no start/end dates > cannot_trial
# invoiced customers, pro plans, no billing_info > cannot_trial

# supported paid plan, with end date > should currently not exist in the DB
