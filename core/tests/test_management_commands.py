import unittest.mock as mock
from io import StringIO

import pytest
from django.core.management import call_command
from shared.config import ConfigHelper

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


@pytest.mark.django_db
def test_update_gitlab_webhook_command(mocker):
    edit_webhook = mocker.patch("shared.torngit.gitlab.Gitlab.edit_webhook")

    get_config = mocker.patch("shared.config._get_config_instance")
    config_helper = ConfigHelper()
    config_helper.set_params(
        {
            "setup": {
                "webhook_url": "http://example.com",
            },
            "gitlab": {
                "webhook_secret": "supersecret",
            },
        }
    )
    get_config.return_value = config_helper

    author = OwnerFactory(service="gitlab")
    repo1 = RepositoryFactory(hookid=123, author=author)
    repo2 = RepositoryFactory(hookid=234, author=author)
    repo3 = RepositoryFactory(hookid=345, author=author)

    call_command(
        "update_gitlab_webhooks",
        stdout=StringIO(),
        stderr=StringIO(),
        starting_repoid=repo2.pk,
    )

    assert edit_webhook.mock_calls == [
        mock.call(
            hookid="234",
            name=None,
            url="http://example.com/webhooks/gitlab",
            events={
                "push_events": True,
                "issues_events": False,
                "merge_requests_events": True,
                "tag_push_events": False,
                "note_events": False,
                "job_events": False,
                "build_events": True,
                "pipeline_events": True,
                "wiki_events": False,
            },
            secret="supersecret",
        ),
        mock.call(
            hookid="345",
            name=None,
            url="http://example.com/webhooks/gitlab",
            events={
                "push_events": True,
                "issues_events": False,
                "merge_requests_events": True,
                "tag_push_events": False,
                "note_events": False,
                "job_events": False,
                "build_events": True,
                "pipeline_events": True,
                "wiki_events": False,
            },
            secret="supersecret",
        ),
    ]
