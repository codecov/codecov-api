import asyncio
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.torngit.exceptions import TorngitObjectNotFoundError

from ..get_final_yaml import GetFinalYamlInteractor


class GetFinalYamlInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)
        asyncio.set_event_loop(asyncio.new_event_loop())

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return GetFinalYamlInteractor(owner, service).execute(*args)

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    @async_to_sync
    async def test_when_commit_has_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.return_value = """
        codecov:
          notify:
            require_ci_to_pass: no
        """
        config = await self.execute(None, self.commit)
        assert config["codecov"]["require_ci_to_pass"] is False

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    @async_to_sync
    async def test_when_commit_has_no_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        config = await self.execute(None, self.commit)
        assert config["codecov"]["require_ci_to_pass"] is True
