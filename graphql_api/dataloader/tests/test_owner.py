import asyncio

from django.test import TestCase, TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.dataloader.owner import load_owner_by_id


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


class OnwerLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.users = [
            OwnerFactory(username="codecov-1"),
            OwnerFactory(username="codecov-2"),
            OwnerFactory(username="codecov-3"),
            OwnerFactory(username="codecov-4"),
            OwnerFactory(username="codecov-5"),
        ]
        self.info = GraphQLResolveInfo()

    async def test_one_user(self):
        user = await load_owner_by_id(self.info, self.users[2].ownerid)
        assert user == self.users[2]

    async def test_a_set_of_users(self):
        users = [
            load_owner_by_id(self.info, self.users[3].ownerid),
            load_owner_by_id(self.info, self.users[2].ownerid),
            load_owner_by_id(self.info, self.users[4].ownerid),
            load_owner_by_id(self.info, self.users[0].ownerid),
            load_owner_by_id(self.info, self.users[1].ownerid),
        ]
        users_loaded = await asyncio.gather(*users)
        assert users_loaded == [
            self.users[3],
            self.users[2],
            self.users[4],
            self.users[0],
            self.users[1],
        ]
