from unittest.mock import patch

import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.torngit.exceptions import TorngitObjectNotFoundError

import services.yaml as yaml


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
        config = yaml.final_commit_yaml(self.commit, None)
        assert config["codecov"]["require_ci_to_pass"] is False

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_no_yaml(self, mock_fetch_yaml):
        mock_fetch_yaml.side_effect = TorngitObjectNotFoundError(
            response_data=404, message="not found"
        )
        config = yaml.final_commit_yaml(self.commit, None)
        assert config["codecov"]["require_ci_to_pass"] is True

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_yaml_with_wrongly_typed_owner_arg(self, mock_fetch_yaml):
        mock_fetch_yaml.return_value = """
        codecov:
          notify:
            require_ci_to_pass: no
        """
        with pytest.raises(TypeError) as exc_info:
            yaml.final_commit_yaml(self.commit, "something else")
        assert (
            str(exc_info.value)
            == "fetch_commit_yaml owner arg must be Owner or None. Provided: <class 'str'>"
        )

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_yaml_with_owner(self, mock_fetch_yaml):
        mock_fetch_yaml.return_value = """
        codecov:
          notify:
            require_ci_to_pass: no
        """
        config = yaml.final_commit_yaml(self.commit, self.org)
        assert config["codecov"]["require_ci_to_pass"] is False

    @patch("services.yaml.fetch_current_yaml_from_provider_via_reference")
    def test_when_commit_has_reserved_to_string_key(self, mock_fetch_yaml):
        mock_fetch_yaml.return_value = """
        codecov:
          notify:
            require_ci_to_pass: no
        to_string: hello
        """
        config = yaml.final_commit_yaml(self.commit, self.org)
        assert config.get("to_string") is None
        assert "to_string" not in config.to_dict()
