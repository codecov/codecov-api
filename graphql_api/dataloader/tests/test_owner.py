import asyncio

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.dataloader.owner import OwnerLoader


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
        loader = OwnerLoader.loader(self.info)
        user = await loader.load(self.users[2].ownerid)
        assert user == self.users[2]

    async def test_a_set_of_users(self):
        loader = OwnerLoader.loader(self.info)
        users = [
            loader.load(self.users[3].ownerid),
            loader.load(self.users[2].ownerid),
            loader.load(self.users[4].ownerid),
            loader.load(self.users[0].ownerid),
            loader.load(self.users[1].ownerid),
        ]
        users_loaded = await asyncio.gather(*users)
        assert users_loaded == [
            self.users[3],
            self.users[2],
            self.users[4],
            self.users[0],
            self.users[1],
        ]
