from datetime import datetime, timedelta

from django.db.models import Q

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
            queryset = ReportSession.objects.filter(
                report__commit__repository__author_id=owner.ownerid,
                report__commit__repository__private=True,
                created_at__gte=datetime.now() - timedelta(days=30),
                report__commit__timestamp__gte=datetime.now() - timedelta(days=60),
                upload_type="uploaded",
            )
        if (
            plan_service.trial_status == TrialStatus.EXPIRED.value
            and plan_service.has_trial_dates
        ):
            queryset = queryset.filter(
                Q(created_at__gte=plan_service.trial_end_date)
                | Q(created_at__lte=plan_service.trial_start_date)
            )

        uploads_used = queryset[:monthly_limit].count()
        return uploads_used
