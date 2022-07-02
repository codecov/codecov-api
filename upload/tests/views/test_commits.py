from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


def test_commits_get_not_allowed(client):
    url = reverse("new_upload.commits", args=["the-repo"])
    assert url == "/upload/the-repo/commits"
    res = client.get(url)
    assert res.status_code == 405


def test_commit_post_empty(db):
    repository = RepositoryFactory.create()
    repository.save()

    owner = OwnerFactory(plan=BASIC_PLAN_NAME)
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.commits",
        args=[repository.name],
    )
    response = client.post(
        url,
        {
            "author": owner.ownerid,
            "message": "The commit message",
            "ci_passed": False,
            "commitid": "commit_sha",
        },
        format="json",
    )
    response_json = response.json()
    print(response.content)
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["author", "commitid", "timestamp", "message", "repository"],
        )
    )
    assert response_json["repository"] == repository.repoid
    assert response_json["author"] == owner.ownerid
    assert response_json["commitid"] == "commit_sha"
