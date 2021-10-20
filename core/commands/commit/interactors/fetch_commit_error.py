from asgiref.sync import sync_to_async

from core.models import ReportErrors
from codecov.commands.base import BaseInteractor


class FetchCommitErrorInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, state, external_id, upload_id):
        # TODO .filter(upload_id=upload_id)

        hardcoded = 24
        errors = ReportErrors.objects.filter(upload_id=hardcoded)
        if state == "error":
            return errors
