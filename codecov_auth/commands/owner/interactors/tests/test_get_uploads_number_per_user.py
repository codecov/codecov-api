from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory

from ..get_uploads_number_per_user import GetUploadsNumberPerUserInteractor


class GetUploadsNumberPerUserInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory()

    async def test_when_called_with_an_owner(self):
        owner = self.user
        uploads = await GetUploadsNumberPerUserInteractor(self, owner).execute(owner)
        assert uploads == 0
