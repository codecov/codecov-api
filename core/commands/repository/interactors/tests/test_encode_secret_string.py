from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.encryption.yaml_secret import yaml_secret_encryptor

from codecov.commands.exceptions import Unauthenticated, ValidationError
from core.tests.factories import OwnerFactory, RepositoryFactory

from ..encode_secret_string import EncodeSecretStringInteractor


class EncodeSecretStringInteractorTest(TransactionTestCase):
    @async_to_sync
    def execute(
        self,
        current_user,
        repo,
        value,
    ):
        return EncodeSecretStringInteractor(None, "github", current_user).execute(
            current_user, repo, value
        )

    def test_encode_secret_string(self):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner, name="repo-1")
        res = self.execute(current_user=owner, repo=repo, value="token-1")
        check_encryptor = yaml_secret_encryptor
        assert check_encryptor.decode(res[7:]) == "token-1"

    def test_validation_error_when_repo_not_found(self):
        owner = OwnerFactory()
        RepositoryFactory(author=owner)
        with pytest.raises(ValidationError):
            self.execute(current_user=owner, repo=None, value="token-1")

    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated) as e:
            self.execute(current_user=AnonymousUser(), repo=None, value="test")
