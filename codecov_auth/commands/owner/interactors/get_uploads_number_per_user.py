from datetime import datetime, timedelta

from django.db.models import Q
from shared.upload.utils import query_monthly_coverage_measurements

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from plan.service import PlanService
from services.redis_configuration import get_redis_connection

redis = get_redis_connection()


class GetUploadsNumberPerUserInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner: Owner):
        plan_service = PlanService(current_org=owner)
        monthly_limit = plan_service.monthly_uploads_limit
        if monthly_limit is not None:
            return query_monthly_coverage_measurements(plan_service=plan_service)
