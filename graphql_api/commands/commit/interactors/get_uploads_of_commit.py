from graphql_api.commands.base import BaseInteractor


class GetUploadsOfCommitInteractor(BaseInteractor):
    def execute(self, commit):
        return []
