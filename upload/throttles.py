import json
import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone
from rest_framework.throttling import BaseThrottle
from shared.reports.enums import UploadType

from plan.constants import USER_PLAN_REPRESENTATIONS
from reports.models import ReportSession
from services.redis_configuration import get_redis_connection
from upload.helpers import _determine_responsible_owner

log = logging.getLogger(__name__)

redis = get_redis_connection()


class UploadsPerCommitThrottle(BaseThrottle):
    def allow_request(self, request, view):
        try:
            repository = view.get_repo()
            commit = view.get_commit(repository)
            new_session_count = ReportSession.objects.filter(
                ~Q(state="error"),
                ~Q(upload_type=UploadType.CARRIEDFORWARD.db_name),
                report__commit=commit,
            ).count()
            max_upload_limit = repository.author.max_upload_limit or 150
            if new_session_count > max_upload_limit:
                log.warning(
                    "Too many uploads to this commit",
                    extra=dict(
                        commit=commit.commitid,
                        repoid=repository.repoid,
                    ),
                )
                return False
            return True
        except ObjectDoesNotExist:
            return True


class UploadsPerWindowThrottle(BaseThrottle):
    def allow_request(self, request, view):
        try:
            repository = view.get_repo()
            commit = view.get_commit(repository)

            if settings.UPLOAD_THROTTLING_ENABLED and repository.private:
                owner = _determine_responsible_owner(repository)
                limit = USER_PLAN_REPRESENTATIONS.get(
                    owner.plan, {}
                ).monthly_uploads_limit
                if limit is not None:
                    did_commit_uploads_start_already = ReportSession.objects.filter(
                        report__commit=commit
                    ).exists()
                    if not did_commit_uploads_start_already:
                        limit = USER_PLAN_REPRESENTATIONS[
                            owner.plan
                        ].monthly_uploads_limit
                        cache_key = f"monthly_upload_usage_{owner.ownerid}"
                        try:
                            uploads_used = redis.get(cache_key)
                            if uploads_used is None:
                                uploads_used = self.query_uploads_used(limit, owner)
                            else:
                                uploads_used = int(uploads_used)
                            redis.set(cache_key, uploads_used, ex=259200)
                        except OSError as e:
                            log.warning(
                                f"Error connecting to redis for rate limit check: {e}",
                                extra=dict(owner=owner.ownerid),
                            )
                            uploads_used = self.query_uploads_used(limit, owner)
                        if uploads_used >= limit:
                            log.warning(
                                "User exceeded its limits for usage",
                                extra=dict(
                                    ownerid=owner.ownerid, repoid=commit.repository_id
                                ),
                            )
                            return False
            return True
        except ObjectDoesNotExist:
            return True

    def query_uploads_used(self, limit, owner):
        return ReportSession.objects.filter(
            report__commit__repository__author_id=owner.ownerid,
            report__commit__repository__private=True,
            created_at__gte=timezone.now() - timedelta(days=30),
            # attempt at making the query more performant by telling the db to not
            # check old commits, which are unlikely to have recent uploads
            report__commit__timestamp__gte=timezone.now() - timedelta(days=60),
            upload_type="uploaded",
        )[:limit].count()
