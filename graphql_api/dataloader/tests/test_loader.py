import pytest
from django.test import TransactionTestCase

from core.tests.factories import CommitFactory
from graphql_api.dataloader.loader import BaseLoader


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


class BaseLoaderTestCase(TransactionTestCase):
    def setUp(self):
        # record type is irrelevant here
        self.record = CommitFactory(message="test commit", commitid="123")

        self.info = GraphQLResolveInfo()

    async def test_unimplemented_load(self):
        loader = BaseLoader.loader(self.info)
        with pytest.raises(NotImplementedError) as err_info:
            await loader.load(self.record.id)

    async def test_default_key(self):
        key = BaseLoader.key(self.record)
        assert key == self.record.id
