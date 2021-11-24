from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory

from ..upload import UploadCommands


class UploadCommandsTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.report_session = CommitFactory()
        self.command = UploadCommands(self.user, "github")

    @patch("core.commands.upload.upload.GetUploadErrorInteractor.execute")
    def test_get_upload_errors_delegate_to_interactor(self, interactor_mock):
        self.command.get_upload_errors(self.report_session)
        interactor_mock.assert_called_once_with(self.report_session)
