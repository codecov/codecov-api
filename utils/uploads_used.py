from loguru import logger
from datetime import datetime, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from codecov_auth.models import Owner
from core.models import Commit, Repository
from plan.constants import TrialStatus
from plan.service import PlanService
from reports.models import ReportSession, ReportType
from user_measurements.models import UserMeasurement
from utils.config import get_config


# default 6 hours for now
cache_time = get_config("setup", "upload_usage_cache_time", default=21600)


def get_uploads_used(redis, plan_service, limit, owner):
    if not settings.UPLOAD_THROTTLING_ENABLED:
        return 0
    cache_key = f"monthly_upload_usage_{owner.ownerid}"
    try:
        uploads_used = redis.get(cache_key)
        if uploads_used is None:
            uploads_used = query_uploads_used(plan_service, limit, owner)
            set_uploads_used(redis, owner, uploads_used)
        else:
            uploads_used = int(uploads_used)

    except OSError as e:
        logger.warning(
            f"Error connecting to redis for rate limit check: {e}",
            extra=dict(owner=owner.ownerid),
        )
        uploads_used = query_uploads_used(plan_service, limit, owner)
    return uploads_used


def set_uploads_used(redis, owner, uploads_used):
    try:
        cache_key = f"monthly_upload_usage_{owner.ownerid}"
        redis.set(cache_key, uploads_used, ex=cache_time)
    except OSError as e:
        logger.warning(
            f"Error connecting to redis for rate limit check: {e}",
            extra=dict(owner=owner.ownerid),
        )


def increment_uploads_used(redis, owner):
    try:
        cache_key = f"monthly_upload_usage_{owner.ownerid}"
        uploads_used = redis.get(cache_key)
        if uploads_used is not None:
            redis.set(cache_key, int(uploads_used) + 1, ex=cache_time)
            # If cache is not already set, we could query here but I would rather defer that to the next request
    except OSError as e:
        logger.warning(
            f"Error connecting to redis for rate limit check: {e}",
            extra=dict(owner=owner.ownerid),
        )


def query_uploads_used(plan_service, limit, owner):
    if not settings.UPLOAD_THROTTLING_ENABLED:
        return 0
    queryset = ReportSession.objects.filter(
        report__commit__repository__author_id=owner.ownerid,
        report__commit__repository__private=True,
        created_at__gte=timezone.now() - timedelta(days=30),
        report__commit__timestamp__gte=timezone.now() - timedelta(days=60),
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

    return queryset[:limit].count()


def query_monthly_coverage_measurements(plan_service: PlanService) -> int:
    owner = plan_service.current_org
    queryset = UserMeasurement.objects.filter(
        owner=owner,
        private_repo=True,
        created_at__gte=timezone.now() - timedelta(days=30),
        report_type="coverage",
    )
    if (
        plan_service.trial_status == TrialStatus.EXPIRED.value
        and plan_service.has_trial_dates
    ):
        queryset = queryset.filter(
            Q(created_at__gte=plan_service.trial_end_date)
            | Q(created_at__lte=plan_service.trial_start_date)
        )
    monthly_limit = plan_service.monthly_uploads_limit
    return queryset[:monthly_limit].count()


def insert_coverage_measurement(
    owner: Owner,
    repo: Repository,
    commit: Commit,
    upload: ReportSession,
    uploader_used: str,
    private_repo: bool,
    report_type: ReportType,
):
    return UserMeasurement.objects.create(
        repo=repo,
        commit=commit,
        upload=upload,
        owner=owner,
        uploader_used=uploader_used,
        private_repo=private_repo,
        report_type=report_type,
    )
