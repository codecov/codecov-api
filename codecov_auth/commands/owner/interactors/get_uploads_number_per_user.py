from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from billing.constants import USER_PLAN_REPRESENTATIONS
from reports.models import ReportSession
from datetime import timedelta
from django.utils import timezone


class GetUploadsNumberPerUserInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner):
        limit = USER_PLAN_REPRESENTATIONS[owner.plan].get(
            "monthly_uploads_limit"
        )
        if limit is not None:
            uploads_used = ReportSession.objects.filter(
                report__commit__repository__author_id=owner.ownerid,
                created_at__gte=timezone.now() - timedelta(days=30),
                report__commit__timestamp__gte=timezone.now() - timedelta(days=60),
                upload_type="uploaded",
            )[:limit].count()
            return uploads_used
