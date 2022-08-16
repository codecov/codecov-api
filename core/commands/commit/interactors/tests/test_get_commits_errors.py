from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from core.tests.factories import CommitErrorFactory, CommitFactory, OwnerFactory
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
    def execute(self, user, commit, error_type):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetCommitErrorsInteractor(current_user, service).execute(
            commit, error_type
        )

    def test_fetch_yaml_error(self):
        errors = async_to_sync(self.execute)(
            user=self.owner,
            commit=self.commit,
            error_type=CommitErrorGeneralType.yaml_error.slug,
        )
        assert len(errors) is 2

    def test_fetch_bot_error(self):
        errors = async_to_sync(self.execute)(
            user=self.owner,
            commit=self.commit,
            error_type=CommitErrorGeneralType.bot_error.slug,
        )
        assert len(errors) is 1
