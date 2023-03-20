from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from graphql_api.types.enums import CommitErrorCode, CommitErrorGeneralType


def errors_by_type(commit, error_type_str):
    error_type = CommitErrorGeneralType(error_type_str)
    error_codes = CommitErrorCode.get_codes_from_type(error_type)
    error_codes_strings = [x.db_string for x in error_codes]
    errors_by_type = commit.errors.filter(error_code__in=error_codes_strings)
    return errors_by_type


class GetCommitErrorsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit, error_type):
        return errors_by_type(commit, error_type_str=error_type)
