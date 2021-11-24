from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from reports.models import UploadError


class GetUploadErrorInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, report_session):
        if not report_session.state == "error":
            return UploadError.objects.none()

        queryset = UploadError.objects.filter(report_session=report_session.id)

        return queryset
