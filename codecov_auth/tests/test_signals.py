from unittest import mock
from unittest.mock import call

import pytest
from django.test import TestCase
from shared.django_apps.codecov_auth.models import Service
from shared.django_apps.codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
    OwnerFactory,
)


@pytest.mark.django_db
def test_shelter_org_token_sync(mocker):
    publish = mocker.patch("google.cloud.pubsub_v1.PublisherClient.publish")

    # this triggers the publish via Django signals
    OrganizationLevelTokenFactory(id=91728376, owner=OwnerFactory(ownerid=111))

    publish.assert_has_calls(
        [
            call(
                "projects/test-project-id/topics/test-topic-id",
                b'{"type": "owner", "sync": "one", "id": 111}',
            ),
            call(
                "projects/test-project-id/topics/test-topic-id",
                b'{"type": "org_token", "sync": "one", "id": 91728376}',
            ),
        ]
    )


@mock.patch("google.cloud.pubsub_v1.PublisherClient.publish")
class TestCodecovAuthSignals(TestCase):
    def test_sync_on_create(self, mock_publish):
        OwnerFactory(ownerid=12345)
        mock_publish.assert_called_once_with(
            "projects/test-project-id/topics/test-topic-id",
            b'{"type": "owner", "sync": "one", "id": 12345}',
        )

    def test_sync_on_update_upload_token_required_for_public_repos(self, mock_publish):
        owner = OwnerFactory(ownerid=12345, upload_token_required_for_public_repos=True)
        owner.upload_token_required_for_public_repos = False
        owner.save()
        mock_publish.assert_has_calls(
            [
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
            ]
        )

    def test_sync_on_update_username(self, mock_publish):
        owner = OwnerFactory(ownerid=12345, username="hello")
        owner.username = "world"
        owner.save()
        mock_publish.assert_has_calls(
            [
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
            ]
        )

    def test_sync_on_update_service(self, mock_publish):
        owner = OwnerFactory(ownerid=12345, service=Service.GITHUB.value)
        owner.service = Service.BITBUCKET.value
        owner.save()
        mock_publish.assert_has_calls(
            [
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
                call(
                    "projects/test-project-id/topics/test-topic-id",
                    b'{"type": "owner", "sync": "one", "id": 12345}',
                ),
            ]
        )

    def test_no_sync_on_update_other_fields(self, mock_publish):
        owner = OwnerFactory(ownerid=12345, name="hello")
        owner.name = "world"
        owner.save()
        mock_publish.assert_called_once_with(
            "projects/test-project-id/topics/test-topic-id",
            b'{"type": "owner", "sync": "one", "id": 12345}',
        )

    @mock.patch("logging.Logger.warning")
    def test_sync_error(self, mock_log, mock_publish):
        mock_publish.side_effect = Exception("publish error")

        OwnerFactory(ownerid=12345)

        # publish is still called, raises an Exception
        mock_publish.assert_called_once_with(
            "projects/test-project-id/topics/test-topic-id",
            b'{"type": "owner", "sync": "one", "id": 12345}',
        )

        mock_log.assert_called_once_with(
            "Failed to publish a message",
            extra=dict(
                data_to_publish={"type": "owner", "sync": "one", "id": 12345},
                error=mock_publish.side_effect,
            ),
        )
