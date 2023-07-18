from datetime import datetime
from typing import List

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import QuerySet

from codecov_auth.models import Owner
from graphql_api.types import plan
from plan.constants import (
    PLANS_THAT_CAN_TRIAL,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    PlanNames,
    TrialStatus,
)


class Command(BaseCommand):
    help = "Sets the initial trial status values for an owner"

    def add_arguments(self, parser: CommandParser) -> None:
        # this can be used to retry if there's an error - restart the command
        # from the last ID printed before failure
        parser.add_argument("--starting_ownerid", type=int)

    def handle(self, *args, **options) -> None:
        owners: QuerySet[Owner] = Owner.objects.all().order_by("ownerid")

        if options.get("starting_ownerid", {}):
            owners = owners.filter(pk__gte=options["starting_ownerid"])

        owners_list: List[Owner] = list(owners)
        for owner in owners_list:
            plan_name = owner.plan
            trial_start_date = owner.trial_start_date
            trial_end_date = owner.trial_end_date
            stripe_customer_id = owner.stripe_customer_id

            if (
                plan_name == PlanNames.BASIC_PLAN_NAME.value
                and trial_start_date is None
                and trial_end_date is None
                and not stripe_customer_id
            ):
                owner.trial_status = TrialStatus.NOT_STARTED.value

            # Only applies to Sentry Paid plans that have started their trial within the last 14 days
            elif (
                plan_name in SENTRY_PAID_USER_PLAN_REPRESENTATIONS
                and (trial_start_date and trial_end_date)
                and (trial_end_date - trial_start_date).days <= 14
            ):
                owner.trial_status = TrialStatus.ONGOING.value

            # Only applies to Sentry paid plans that underwent their trial, or sentry plans that have expired and are now back to basic plan
            elif (
                plan_name in SENTRY_PAID_USER_PLAN_REPRESENTATIONS
                and trial_end_date
                and datetime.utcnow() > trial_end_date
            ) or (
                plan_name == PlanNames.BASIC_PLAN_NAME.value
                and trial_start_date
                and trial_end_date
            ):
                owner.trial_status = TrialStatus.EXPIRED.value
            # Plans that don't offer trial or currently/previously paying customers that never trialed.
            elif (
                plan_name not in PLANS_THAT_CAN_TRIAL
                # I can probably get rid of this condition and use the 'or' below instead?
                or (
                    stripe_customer_id
                    and owner.stripe_subscription_id
                    and trial_start_date == None
                    and trial_end_date == None
                )
                or (
                    stripe_customer_id
                    and trial_start_date == None
                    and trial_end_date == None
                )
            ):
                owner.trial_status = TrialStatus.CANNOT_TRIAL.value
            else:
                pass

            owner.save()
