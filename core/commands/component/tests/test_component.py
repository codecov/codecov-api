from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov.commands.exceptions import Unauthenticated, Unauthorized, ValidationError

from ..component import ComponentCommands


class MockSignature:
    def apply_async(self):
        pass


class ComponentCommandsTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="test-user")
        self.org = OwnerFactory(username="test-org", admins=[self.owner.pk])
        self.owner.organizations = [self.org.pk]
        self.repo = RepositoryFactory(author=self.org)
        self.command = ComponentCommands(self.owner, "github")

    @patch("services.task.TaskService.delete_component_measurements")
    def test_delete_component_measurements(self, mocked_delete_timeseries):
        self.command.delete_component_measurements(
            owner_username=self.org.username,
            repo_name=self.repo.name,
            component_id="component1",
        )

        mocked_delete_timeseries.assert_called_once_with(self.repo.pk, "component1")

    def test_delete_component_measurements_unauthenticated(self):
        self.command = ComponentCommands(None, "github")

        with self.assertRaises(Unauthenticated):
            self.command.delete_component_measurements(
                owner_username=self.org.username,
                repo_name=self.repo.name,
                component_id="component1",
            )

    def test_delete_component_measurements_owner_not_found(self):
        with self.assertRaises(ValidationError):
            self.command.delete_component_measurements(
                owner_username="nonexistent",
                repo_name=self.repo.name,
                component_id="component1",
            )

    def test_delete_component_measurements_repo_not_found(self):
        with self.assertRaises(ValidationError):
            self.command.delete_component_measurements(
                owner_username=self.org.username,
                repo_name="nonexistent",
                component_id="component1",
            )

    def test_delete_component_measurements_not_admin(self):
        self.org.admins = []
        self.org.save()

        with self.assertRaises(Unauthorized):
            self.command.delete_component_measurements(
                owner_username=self.org.username,
                repo_name=self.repo.name,
                component_id="component1",
            )

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.get_config")
    @patch("services.task.TaskService.delete_component_measurements")
    def test_delete_component_measurements_self_hosted_admin(
        self, mocked_delete_timeseries, get_config_mock
    ):
        get_config_mock.return_value = [
            {"service": "github", "username": self.owner.username},
        ]

        self.command.delete_component_measurements(
            owner_username=self.org.username,
            repo_name=self.repo.name,
            component_id="component1",
        )

        mocked_delete_timeseries.assert_called_once_with(self.repo.pk, "component1")

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.get_config")
    def test_delete_component_measurements_self_hosted_non_admin(self, get_config_mock):
        get_config_mock.return_value = [
            {"service": "github", "username": "someone-else"},
        ]

        with self.assertRaises(Unauthorized):
            self.command.delete_component_measurements(
                owner_username=self.org.username,
                repo_name=self.repo.name,
                component_id="component1",
            )

    @patch("services.task.TaskService._create_signature")
    def test_delete_component_measurements_signature_created(
        self, mocked_create_signature
    ):
        self.command.delete_component_measurements(
            owner_username=self.org.username,
            repo_name=self.repo.name,
            component_id="component1",
        )

        mocked_create_signature.return_value = MockSignature()
        mocked_create_signature.assert_called()
