import logging
from typing import Optional

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from core.models import Commit
from reports.models import CommitReport, UploadError

log = logging.getLogger(__name__)


class GetLatestUploadErrorInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit: Commit) -> Optional[dict]:
        try:
            return self._get_latest_error(commit)
        except Exception as e:
            log.error(f"Error fetching upload error: {e}")
            return None

    def _get_latest_error(self, commit: Commit) -> Optional[dict]:
        latest_error = self._fetch_latest_error(commit)
        if not latest_error:
            return None

        return {
            "error_code": latest_error.error_code,
            "error_message": latest_error.error_params.get("error_message"),
        }

    def _fetch_latest_error(self, commit: Commit) -> Optional[UploadError]:
        return (
            UploadError.objects.filter(
                report_session__report__commit=commit,
                report_session__report__report_type=CommitReport.ReportType.TEST_RESULTS,
            )
            .only("error_code", "error_params")
            .order_by("-created_at")
            .first()
        )
