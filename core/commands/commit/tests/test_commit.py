from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from ..commit import CommitCommands


class CommitCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()
        self.command = CommitCommands(self.user, "github")

    @patch("core.commands.commit.commit.FetchCommitInteractor.execute")
    def test_fetch_commit_delegate_to_interactor(self, interactor_mock):
        commit_id = "123"
        self.command.fetch_commit(self.repository, commit_id)
        interactor_mock.assert_called_once_with(self.repository, commit_id)

    @patch("core.commands.commit.commit.FetchCommitsInteractor.execute")
    def test_fetch_commits_delegate_to_interactor(self, interactor_mock):
        self.filters = None
        self.command.fetch_commits(self.repository, self.filters)
        interactor_mock.assert_called_once_with(self.repository, self.filters)

    @patch("core.commands.commit.commit.GetUploadsOfCommitInteractor.execute")
    def test_get_uploads_of_commit_delegate_to_interactor(self, interactor_mock):
        commit = CommitFactory()
        self.command.get_uploads_of_commit(commit)
        interactor_mock.assert_called_once_with(commit)

    @patch("core.commands.commit.commit.GetFinalYamlInteractor.execute")
    def test_get_final_yaml_delegate_to_interactor(self, interactor_mock):
        self.command.get_final_yaml(self.commit)
        interactor_mock.assert_called_once_with(self.commit)

    @patch("core.commands.commit.commit.GetFileContentInteractor.execute")
    def test_get_file_content_delegate_to_interactor(self, interactor_mock):
        self.command.get_file_content(self.commit, "path/to/file")
        interactor_mock.assert_called_once_with(self.commit, "path/to/file")
