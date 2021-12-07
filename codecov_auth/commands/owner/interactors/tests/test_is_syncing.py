from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory

from ..is_syncing import IsSyncingInteractor


class IsSyncingInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    @patch("services.refresh.RefreshService.is_refreshing")
    @async_to_sync
    async def test_call_is_refreshing(self, mock_is_refreshing):
        mock_is_refreshing.return_value = True
        res = await IsSyncingInteractor(self.user, "github").execute()
        assert res is True
        mock_is_refreshing.assert_called()
        print(mock_is_refreshing)
