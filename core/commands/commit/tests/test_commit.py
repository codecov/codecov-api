from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from ..commit import CommitCommands


class CommitCommandsTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()
        self.pull = PullFactory(repository_id=self.repository.repoid)
        self.command = CommitCommands(self.owner, "github")

    @patch("core.commands.commit.commit.GetFinalYamlInteractor.execute")
    def test_get_final_yaml_delegate_to_interactor(self, interactor_mock):
        self.command.get_final_yaml(self.commit)
        interactor_mock.assert_called_once_with(self.commit)

    @patch("core.commands.commit.commit.GetFileContentInteractor.execute")
    def test_get_file_content_delegate_to_interactor(self, interactor_mock):
        self.command.get_file_content(self.commit, "path/to/file")
        interactor_mock.assert_called_once_with(self.commit, "path/to/file")

    @patch("core.commands.commit.commit.GetCommitErrorsInteractor.execute")
    def test_get_commit_errors_delegate_to_interactor(self, interactor_mock):
        self.command.get_commit_errors(self.commit, "YAML_ERROR")
        interactor_mock.assert_called_once_with(self.commit, "YAML_ERROR")

    @patch("core.commands.commit.commit.GetUploadsNumberInteractor.execute")
    def test_get_uploads_number_delegate_to_interactor(self, interactor_mock):
        self.command.get_uploads_number(self.commit)
        interactor_mock.assert_called_once_with(self.commit)

    @patch("core.commands.commit.commit.GetLatestUploadErrorInteractor.execute")
    def test_get_latest_upload_error_delegate_to_interactor(self, interactor_mock):
        self.command.get_latest_upload_error(self.commit)
        interactor_mock.assert_called_once_with(self.commit)
