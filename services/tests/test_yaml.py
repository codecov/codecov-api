from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.torngit.exceptions import TorngitObjectNotFoundError

import services.yaml as yaml
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory


class YamlServiceTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.return_value = """
        codecov:
          notify:
            require_ci_to_pass: no
        """
        config = yaml.final_commit_yaml(self.commit, AnonymousUser())
        assert config["codecov"]["require_ci_to_pass"] is False

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_no_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        config = yaml.final_commit_yaml(self.commit, AnonymousUser())
        assert config["codecov"]["require_ci_to_pass"] is True
