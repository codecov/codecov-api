import os
from unittest.mock import call

import pytest
from django.test import override_settings
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory


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
    repo = RepositoryFactory(repoid=91728376, author=OwnerFactory(ownerid=555))

    # triggers publish on create
    publish.assert_has_calls(
        [
            call(
                "projects/test-project-id/topics/test-topic-id",
                b'{"type": "owner", "sync": "one", "id": 555}',
            ),
            call(
                "projects/test-project-id/topics/test-topic-id",
                b'{"type": "repo", "sync": "one", "id": 91728376}',
            ),
        ]
    )

    repo.upload_token = "b69cf44c-89d8-48c2-80c9-5508610d3ced"
    repo.save()

    publish_calls = publish.call_args_list
    assert len(publish_calls) == 3

    # triggers publish on update
    assert publish_calls[2] == call(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "repo", "sync": "one", "id": 91728376}',
    )

    repo.message = "foo"
    repo.save()

    publish_calls = publish.call_args_list
    # does not trigger another publish
    assert len(publish_calls) == 3


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
    owner = OwnerFactory(ownerid=555)
    commit = CommitFactory(
        id=167829367,
        branch="random:branch",
        author=owner,
        repository=RepositoryFactory(author=owner),
    )

    publish_calls = publish.call_args_list
    # 3x cause there's a signal triggered when the commit factory requires a Repository and Owner
    # which can't be null
    assert len(publish_calls) == 3

    # triggers publish on update
    assert publish_calls[2] == call(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "commit", "sync": "one", "id": 167829367}',
    )

    commit.branch = "normal-incompatible-branch"
    commit.save()

    publish_calls = publish.call_args_list
    # does not trigger another publish since unchanged length
    assert len(publish_calls) == 3
