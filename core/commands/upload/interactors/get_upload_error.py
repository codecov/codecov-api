from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from graphql_api.types.enums import UploadState
from reports.models import UploadError


class GetUploadErrorInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, report_session):
        if not report_session.state == UploadState.ERROR.value:
            return UploadError.objects.none()

        queryset = UploadError.objects.filter(report_session=report_session.id)

        return queryset
