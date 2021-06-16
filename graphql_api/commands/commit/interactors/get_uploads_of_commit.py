from graphql_api.commands.base import BaseInteractor

from shared.utils.sessions import Session


class GetUploadsOfCommitInteractor(BaseInteractor):
    def execute(self, commit):
        uploads_raw = commit.report.get("sessions", {}).values()
        return [Session.parse_session(**upload) for upload in uploads_raw]
