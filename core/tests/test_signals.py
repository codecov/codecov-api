import os
from unittest.mock import call

import pytest
from django.test import override_settings
from shared.django_apps.core.tests.factories import CommitFactory

from core.tests.factories import RepositoryFactory


@override_settings(
    SHELTER_PUBSUB_PROJECT_ID="test-project-id",
    SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID="test-topic-id",
)
@pytest.mark.django_db
def test_shelter_repo_sync(mocker):
    # this prevents the pubsub SDK from trying to load credentials
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost"

    publish = mocker.patch("google.cloud.pubsub_v1.PublisherClient.publish")

    # this triggers the publish via Django signals
    repo = RepositoryFactory(repoid=91728376)

    # triggers publish on create
    publish.assert_called_once_with(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "repo", "sync": "one", "id": 91728376}',
    )

    repo.upload_token = "b69cf44c-89d8-48c2-80c9-5508610d3ced"
    repo.save()

    publish_calls = publish.call_args_list
    assert len(publish_calls) == 2

    # triggers publish on update
    assert publish_calls[1] == call(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "repo", "sync": "one", "id": 91728376}',
    )

    repo.message = "foo"
    repo.save()

    publish_calls = publish.call_args_list
    # does not trigger another publish
    assert len(publish_calls) == 2


@override_settings(
    SHELTER_PUBSUB_PROJECT_ID="test-project-id",
    SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID="test-topic-id",
)
@pytest.mark.django_db
def test_shelter_commit_sync(mocker):
    # this prevents the pubsub SDK from trying to load credentials
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost"
    publish = mocker.patch("google.cloud.pubsub_v1.PublisherClient.publish")

    # this triggers the publish via Django signals - has to have this format
    commit = CommitFactory(id=167829367, branch="random:branch")

    publish_calls = publish.call_args_list
    # Twice cause there's a signal triggered when the commit factory creates a Repository
    # which can't be null
    assert len(publish_calls) == 2

    # triggers publish on update
    assert publish_calls[1] == call(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "commit", "sync": "one", "id": 167829367}',
    )

    commit.branch = "normal-incompatible-branch"
    commit.save()

    publish_calls = publish.call_args_list
    # does not trigger another publish since unchanged length
    assert len(publish_calls) == 2
