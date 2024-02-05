import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from rest_framework.throttling import BaseThrottle
from shared.reports.enums import UploadType

from plan.service import PlanService
from reports.models import ReportSession
from services.redis_configuration import get_redis_connection
from upload.helpers import _determine_responsible_owner
from utils.uploads_used import get_uploads_used

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
                plan_service = PlanService(current_org=owner)
                limit = plan_service.monthly_uploads_limit
                if limit is not None:
                    did_commit_uploads_start_already = ReportSession.objects.filter(
                        report__commit=commit
                    ).exists()
                    if not did_commit_uploads_start_already:

                        if get_uploads_used(redis, plan_service, limit, owner) >= limit:
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
