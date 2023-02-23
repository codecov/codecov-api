from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory

from ..flag import FlagCommands


class FlagCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="test-user")
        self.owner = OwnerFactory(username="test-org", admins=[self.user.pk])
        self.repo = RepositoryFactory(author=self.owner)
        self.command = FlagCommands(self.user, "github")
        self.flag = RepositoryFlagFactory(repository=self.repo, flag_name="test-flag")

    def test_delete_flag(self):
        self.command.delete_flag(
            owner_username=self.owner.username,
            repo_name=self.repo.name,
            flag_name=self.flag.flag_name,
        )

        self.flag.refresh_from_db()
        assert self.flag.deleted is True

    def test_delete_flag_unauthenticated(self):
        self.command.current_user = AnonymousUser()

        with self.assertRaises(Unauthenticated):
            self.command.delete_flag(
                owner_username=self.owner.username,
                repo_name=self.repo.name,
                flag_name=self.flag.flag_name,
            )

    def test_delete_flag_owner_not_found(self):
        with self.assertRaises(ValidationError):
            self.command.delete_flag(
                owner_username="nonexistent",
                repo_name=self.repo.name,
                flag_name=self.flag.flag_name,
            )

    def test_delete_flag_repo_not_found(self):
        with self.assertRaises(ValidationError):
            self.command.delete_flag(
                owner_username=self.owner.username,
                repo_name="nonexistent",
                flag_name=self.flag.flag_name,
            )

    def test_delete_flag_not_admin(self):
        self.owner.admins = []
        self.owner.save()

        with self.assertRaises(Unauthorized):
            self.command.delete_flag(
                owner_username=self.owner.username,
                repo_name=self.repo.name,
                flag_name=self.flag.flag_name,
            )

    def test_delete_flag_not_found(self):
        # noop
        self.command.delete_flag(
            owner_username=self.owner.username,
            repo_name=self.repo.name,
            flag_name="nonexistent",
        )
