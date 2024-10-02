from unittest.mock import patch

import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.torngit.exceptions import TorngitObjectNotFoundError

from ..get_file_content import GetFileContentInteractor


class MockedProviderAdapter:
    async def get_source(self, commit, path):
        return {
            "content": b"""
        def function_1:
            pass
        """
        }


class MockedStringProviderAdapter:
    async def get_source(self, commit, path):
        return {
            "content": """
        def function_1:
            pass
        """
        }


class GetFileContentInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.repository = RepositoryFactory()
        self.commit = CommitFactory()

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return GetFileContentInteractor(owner, service).execute(*args)

    @patch("services.repo_providers.RepoProviderService.async_get_adapter")
    @pytest.mark.asyncio
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

    @patch("services.repo_providers.RepoProviderService.async_get_adapter")
    @pytest.mark.asyncio
    async def test_when_path_has_no_file(self, mock_provider_adapter):
        mock_provider_adapter.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        file_content = await self.execute(None, self.commit, "path")
        assert file_content is None

    @patch("services.repo_providers.RepoProviderService.async_get_adapter")
    @pytest.mark.asyncio
    async def test_when_path_has_file_string_response(self, mock_provider_adapter):
        mock_provider_adapter.return_value = MockedStringProviderAdapter()

        file_content = await self.execute(None, self.commit, "path/to/file")
        assert (
            file_content
            == """
        def function_1:
            pass
        """
        )
