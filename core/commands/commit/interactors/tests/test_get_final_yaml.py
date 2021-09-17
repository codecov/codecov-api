from asgiref.sync import async_to_sync
import asyncio
import pytest
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth.models import AnonymousUser
from shared.torngit.exceptions import TorngitObjectNotFoundError

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory

from ..get_final_yaml import GetFinalYamlInteractor


class GetFinalYamlInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)
        asyncio.set_event_loop(asyncio.new_event_loop())

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return GetFinalYamlInteractor(current_user, service).execute(*args)

    @patch(
        "core.commands.commit.interactors.get_final_yaml.fetch_current_yaml_from_provider_via_reference"
    )
    @async_to_sync
    async def test_when_commit_has_yaml(self, mock_fetch_yaml):
        f = asyncio.Future()
        f.set_result(
            """
        codecov:
          notify:
            require_ci_to_pass: no
        """
        )
        mock_fetch_yaml.return_value = f
        config = await self.execute(None, self.commit)
        assert config["codecov"]["require_ci_to_pass"] is False

    @patch(
        "core.commands.commit.interactors.get_final_yaml.fetch_current_yaml_from_provider_via_reference"
    )
    @async_to_sync
    async def test_when_commit_has_no_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        config = await self.execute(None, self.commit)
        print(config)
        assert config["codecov"]["require_ci_to_pass"] is True
