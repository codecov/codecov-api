from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitErrorFactory,
    CommitFactory,
    OwnerFactory,
)

from graphql_api.types.enums import CommitErrorGeneralType

from ..get_commit_errors import GetCommitErrorsInteractor


class GetCommitErrorsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory()
        self.commit = CommitFactory()
        self.yaml_commit_error = CommitErrorFactory(
            commit=self.commit, error_code="invalid_yaml"
        )
        self.yaml_commit_error_2 = CommitErrorFactory(
            commit=self.commit, error_code="yaml_client_error"
        )
        self.bot_commit_error = CommitErrorFactory(
            commit=self.commit, error_code="repo_bot_invalid"
        )

    # helper to execute the interactor
    def execute(self, owner, commit, error_type):
        service = owner.service if owner else "github"
        return GetCommitErrorsInteractor(owner, service).execute(commit, error_type)

    def test_fetch_yaml_error(self):
        errors = async_to_sync(self.execute)(
            owner=self.owner,
            commit=self.commit,
            error_type=CommitErrorGeneralType.yaml_error.value,
        )
        assert len(errors) == 2

    def test_fetch_bot_error(self):
        errors = async_to_sync(self.execute)(
            owner=self.owner,
            commit=self.commit,
            error_type=CommitErrorGeneralType.bot_error.value,
        )
        assert len(errors) == 1
