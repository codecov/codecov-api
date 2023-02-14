import logging
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone
from rest_framework.throttling import BaseThrottle
from shared.reports.enums import UploadType

from billing.constants import USER_PLAN_REPRESENTATIONS
from core.models import Commit, Repository
from reports.models import ReportSession
from upload.helpers import _determine_responsible_owner
from utils.config import get_config

log = logging.getLogger(__name__)


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
                limit = USER_PLAN_REPRESENTATIONS.get(owner.plan, {}).get(
                    "monthly_uploads_limit"
                )
                if limit is not None:
                    did_commit_uploads_start_already = ReportSession.objects.filter(
                        report__commit=commit
                    ).exists()
                    if not did_commit_uploads_start_already:
                        limit = USER_PLAN_REPRESENTATIONS[owner.plan].get(
                            "monthly_uploads_limit"
                        )
                        uploads_used = ReportSession.objects.filter(
                            report__commit__repository__author_id=owner.ownerid,
                            report__commit__repository__private=True,
                            created_at__gte=timezone.now() - timedelta(days=30),
                            # attempt at making the query more performant by telling the db to not
                            # check old commits, which are unlikely to have recent uploads
                            report__commit__timestamp__gte=timezone.now()
                            - timedelta(days=60),
                            upload_type="uploaded",
                        )[:limit].count()
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
