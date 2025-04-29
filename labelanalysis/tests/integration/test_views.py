from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    RepositoryTokenFactory,
)

from labelanalysis.views import EMPTY_RESPONSE


def test_simple_label_analysis_call_flow(db):
    commit = CommitFactory.create(repository__active=True)
    base_commit = CommitFactory.create(repository=commit.repository)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("create_label_analysis")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    payload = {
        "base_commit": base_commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
    }
    response = client.post(
        url,
        payload,
        format="json",
    )
    assert response.status_code == 201
    assert response.json() == EMPTY_RESPONSE

    get_url = reverse("view_label_analysis", kwargs={"external_id": "doesnotmatter"})
    response = client.get(get_url, format="json")
    assert response.status_code == 200
    assert response.json() == EMPTY_RESPONSE


def test_simple_label_analysis_put_labels(db):
    commit = CommitFactory.create(repository__active=True)
    base_commit = CommitFactory.create(repository=commit.repository)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)

    patch_url = reverse("view_label_analysis", kwargs={"external_id": "doesnotmatter"})
    response = client.patch(
        patch_url,
        format="json",
        data={
            "requested_labels": ["label_1", "label_2", "label_3"],
            "base_commit": base_commit.commitid,
            "head_commit": commit.commitid,
        },
    )
    assert response.status_code == 200
    assert response.json() == EMPTY_RESPONSE
