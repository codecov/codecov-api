import unittest.mock as mock
import uuid
from io import StringIO

import fakeredis
import pytest
from django.core.management import call_command
from shared.config import ConfigHelper

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory


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
        }
    )
    get_config.return_value = config_helper

    author = OwnerFactory(service="gitlab")
    repo1 = RepositoryFactory(hookid=123, author=author, webhook_secret=None)
    repo2 = RepositoryFactory(hookid=234, author=author, webhook_secret=None)
    repo3 = RepositoryFactory(hookid=345, author=author, webhook_secret=None)

    call_command(
        "update_gitlab_webhooks",
        stdout=StringIO(),
        stderr=StringIO(),
        starting_repoid=repo2.pk,
    )

    repo1.refresh_from_db()
    assert repo1.webhook_secret is None
    repo2.refresh_from_db()
    assert repo2.webhook_secret is not None
    repo3.refresh_from_db()
    assert repo3.webhook_secret is not None

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
            secret=repo2.webhook_secret,
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
            secret=repo3.webhook_secret,
        ),
    ]


@pytest.mark.django_db
def test_backfill_commits_command(mocker):
    storage_redis = fakeredis.FakeStrictRedis()
    celery_redis = fakeredis.FakeStrictRedis()
    mocker.patch(
        "core.management.commands.backfill_commits.get_storage_redis",
        return_value=storage_redis,
    )
    mocker.patch(
        "core.management.commands.backfill_commits.get_celery_redis",
        return_value=celery_redis,
    )

    backfill_commits = mocker.patch("services.task.TaskService.backfill_commit_data")

    get_config = mocker.patch("shared.config._get_config_instance")
    config_helper = ConfigHelper()
    config_helper.set_params(
        {
            "setup": {
                "webhook_url": "http://example.com",
            },
        }
    )
    get_config.return_value = config_helper

    commit1 = CommitFactory()
    commit2 = CommitFactory()
    commit3 = CommitFactory()

    # undrained queue

    celery_redis.lpush(
        "backfill_commits", "placeholder"
    )  # mimic > 0 items in the queue
    call_command(
        "backfill_commits",
        stdout=StringIO(),
        stderr=StringIO(),
        batch_size=2,
    )

    # noop - waits for queue to drain
    assert backfill_commits.mock_calls == []
    celery_redis.delete("backfill_commits")

    # 1st batch

    call_command(
        "backfill_commits",
        stdout=StringIO(),
        stderr=StringIO(),
        batch_size=2,
    )

    assert backfill_commits.mock_calls == [
        mock.call(commitid=commit3.commitid),
        mock.call(commitid=commit2.commitid),
    ]

    backfill_commits.reset_mock()

    # 2nd batch

    call_command(
        "backfill_commits",
        stdout=StringIO(),
        stderr=StringIO(),
        batch_size=2,
    )

    assert backfill_commits.mock_calls == [
        mock.call(commitid=commit1.commitid),
    ]

    backfill_commits.reset_mock()

    # empty batch

    call_command(
        "backfill_commits",
        stdout=StringIO(),
        stderr=StringIO(),
        batch_size=2,
    )

    assert backfill_commits.mock_calls == []
