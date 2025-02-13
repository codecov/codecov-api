from unittest.mock import call

import pytest
from shared.django_apps.codecov_auth.tests.factories import OwnerFactory
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory


@pytest.mark.django_db
def test_shelter_repo_sync(mocker):
    publish = mocker.patch("google.cloud.pubsub_v1.PublisherClient.publish")

    # this triggers the publish via Django signals
    repo = RepositoryFactory(
        repoid=91728376, author=OwnerFactory(ownerid=555), private=False
    )

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

    # Does not trigger another publish with untracked field
    repo.message = "foo"
    repo.save()

    publish_calls = publish.call_args_list
    assert len(publish_calls) == 3

    # Triggers call when owner is changed
    repo.author = OwnerFactory(ownerid=888)
    repo.save()

    publish_calls = publish.call_args_list
    # 1 is for the new owner created
    assert len(publish_calls) == 5
    publish.assert_has_calls(
        [
            call(
                "projects/test-project-id/topics/test-topic-id",
                b'{"type": "owner", "sync": "one", "id": 888}',
            ),
        ]
    )

    # Triggers call when private is changed
    repo.private = True
    repo.save()

    # publish_calls = publish.call_args_list
    assert len(publish_calls) == 6


@pytest.mark.django_db
def test_shelter_commit_sync(mocker):
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
