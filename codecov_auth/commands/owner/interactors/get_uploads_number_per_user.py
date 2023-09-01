from datetime import datetime, timedelta

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from plan.constants import USER_PLAN_REPRESENTATIONS, TrialStatus
from plan.service import PlanService
from reports.models import ReportSession


class GetUploadsNumberPerUserInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner: Owner):
        plan_service = PlanService(current_org=owner)
        monthly_limit = plan_service.monthly_uploads_limit
        if monthly_limit is not None:
            # This should be mirroring upload/helpers.py::check_commit_upload_constraints behavior
            # We should put this in a centralized place
            created_at = datetime.utcnow() - timedelta(days=30)
            if (
                plan_service.trial_status == TrialStatus.EXPIRED.value
                and plan_service.has_trial_dates
            ):
                trial_duration_in_days = plan_service.trial_duration_in_days()
                time_since_trial_end_in_days = (
                    datetime.utcnow() - plan_service.trial_end_date
                ).days
                if time_since_trial_end_in_days < trial_duration_in_days:
                    created_at = plan_service.trial_end_date

            uploads_used = ReportSession.objects.filter(
                upload_type="uploaded",
                report__commit__repository__author_id=owner.ownerid,
                report__commit__repository__private=True,
                created_at__gte=created_at,
                report__commit__timestamp__gte=datetime.utcnow() - timedelta(days=60),
            )[:monthly_limit].count()
            return uploads_used
