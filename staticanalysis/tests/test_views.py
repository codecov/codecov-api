from uuid import uuid4

from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    RepositoryTokenFactory,
)

from staticanalysis.views import EMPTY_RESPONSE


def test_simple_static_analysis_call_no_uploads_yet(db):
    commit = CommitFactory.create(repository__active=True)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("staticanalyses-list")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    some_uuid, second_uuid = uuid4(), uuid4()
    response = client.post(
        url,
        {
            "commit": commit.commitid,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": some_uuid,
                },
                {
                    "filepath": "banana.cpp",
                    "file_hash": second_uuid,
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.json() == EMPTY_RESPONSE


def test_static_analysis_finish(db):
    commit = CommitFactory.create(repository__active=True)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(
        reverse("staticanalyses-finish", kwargs={"external_id": "doesnotmatter"})
    )
    assert response.status_code == 201
