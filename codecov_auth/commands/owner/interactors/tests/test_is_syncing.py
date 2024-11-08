from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from ..is_syncing import IsSyncingInteractor


class IsSyncingInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    @patch("services.refresh.RefreshService.is_refreshing")
    @async_to_sync
    async def test_call_is_refreshing(self, mock_is_refreshing):
        mock_is_refreshing.return_value = True
        res = await IsSyncingInteractor(self.owner, "github").execute()
        assert res is True
        mock_is_refreshing.assert_called()
