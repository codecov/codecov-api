import os

import pytest
from django.test import override_settings

from codecov_auth.tests.factories import OrganizationLevelTokenFactory


@override_settings(
    SHELTER_PUBSUB_PROJECT_ID="test-project-id",
    SHELTER_PUBSUB_SYNC_REPO_TOPIC_ID="test-topic-id",
)
@pytest.mark.django_db
def test_shelter_org_token_sync(mocker):
    # this prevents the pubsub SDK from trying to load credentials
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost"

    publish = mocker.patch("google.cloud.pubsub_v1.PublisherClient.publish")

    # this triggers the publish via Django signals
    OrganizationLevelTokenFactory(id=91728376)

    publish.assert_called_once_with(
        "projects/test-project-id/topics/test-topic-id",
        b'{"type": "org_token", "sync": "one", "id": 91728376}',
    )
