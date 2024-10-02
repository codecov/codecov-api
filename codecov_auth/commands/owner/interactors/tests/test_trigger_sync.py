from unittest.mock import patch

import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthenticated

from ..trigger_sync import TriggerSyncInteractor


class IsSyncingInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await TriggerSyncInteractor(None, "github").execute()

    @patch("services.refresh.RefreshService.trigger_refresh")
    async def test_call_is_refreshing(self, mock_trigger_refresh):
        await TriggerSyncInteractor(self.owner, "github").execute()
        mock_trigger_refresh.assert_called_once_with(
            self.owner.ownerid,
            self.owner.username,
            using_integration=False,
            manual_trigger=True,
        )
