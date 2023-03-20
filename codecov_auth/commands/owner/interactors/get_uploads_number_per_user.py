from datetime import timedelta

from django.utils import timezone

from billing.constants import USER_PLAN_REPRESENTATIONS
from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from reports.models import ReportSession


class GetUploadsNumberPerUserInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner):
        limit = USER_PLAN_REPRESENTATIONS[owner.plan].get("monthly_uploads_limit")
        if limit is not None:
            # This should be mirroring upload/helpers.py::check_commit_upload_constraints behavior
            # We should put this in a centralized place
            uploads_used = ReportSession.objects.filter(
                report__commit__repository__author_id=owner.ownerid,
                report__commit__repository__private=True,
                created_at__gte=timezone.now() - timedelta(days=30),
                report__commit__timestamp__gte=timezone.now() - timedelta(days=60),
                upload_type="uploaded",
            )[:limit].count()
            return uploads_used
