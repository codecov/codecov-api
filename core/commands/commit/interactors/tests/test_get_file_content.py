import asyncio
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.torngit.exceptions import TorngitObjectNotFoundError

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from ..get_file_content import GetFileContentInteractor


class MockedProviderAdapter:
    async def get_source(self, commit, path):
        return {
            "content": b"""
        def function_1:
            pass
        """
        }


class GetFileContentInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetFileContentInteractor(current_user, service).execute(*args)

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @async_to_sync
    async def test_when_path_has_file(self, mock_provider_adapter):
        mock_provider_adapter.return_value = MockedProviderAdapter()

        file_content = await self.execute(None, self.commit, "path/to/file")
        assert (
            file_content
            == """
        def function_1:
            pass
        """
        )

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    @async_to_sync
    async def test_when_path_has_no_file(self, mock_provider_adapter):
        mock_provider_adapter.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        file_content = await self.execute(None, self.commit, "path")
        assert file_content == None
