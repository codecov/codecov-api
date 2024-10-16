import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.encryption.yaml_secret import yaml_secret_encryptor

from codecov.commands.exceptions import Unauthenticated, ValidationError

from ..encode_secret_string import EncodeSecretStringInteractor


class EncodeSecretStringInteractorTest(TransactionTestCase):
    @async_to_sync
    def execute(self, owner, repo_name, value):
        return EncodeSecretStringInteractor(owner, "github").execute(
            owner, repo_name, value
        )

    def test_encode_secret_string(self):
        owner = OwnerFactory()
        RepositoryFactory(author=owner, name="repo-1")
        res = self.execute(owner, repo_name="repo-1", value="token-1")
        check_encryptor = yaml_secret_encryptor
        assert "token-1" in check_encryptor.decode(res[7:])

    def test_validation_error_when_repo_not_found(self):
        owner = OwnerFactory()
        with pytest.raises(ValidationError):
            self.execute(owner, repo_name=None, value="token-1")

    def test_user_is_not_authenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(None, repo_name=None, value="test")
