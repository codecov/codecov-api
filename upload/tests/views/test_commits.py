import pytest
from django.forms import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from upload.views.commits import CommitViews


def test_commits_get_not_allowed(client):
    url = reverse("new_upload.commits", args=["the-repo"])
    assert url == "/upload/the-repo/commits"
    res = client.get(url)
    assert res.status_code == 405


def test_get_repo(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    repository.save()
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo=repository.name)
    recovered_repo = upload_views.get_repo()
    assert recovered_repo == repository


def test_get_repo_error(db):
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="repo_missing")
    with pytest.raises(ValidationError):
        upload_views.get_repo()


def test_get_queryset(db):
    target_repo = RepositoryFactory(name="the_repo", author__username="codecov")
    random_repo = RepositoryFactory()
    target_commit_1 = CommitFactory(repository=target_repo)
    target_commit_2 = CommitFactory(repository=target_repo)
    random_commit = CommitFactory(repository=random_repo)
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo=target_repo.name)
    recovered_commits = upload_views.get_queryset()
    assert target_commit_1 in recovered_commits
    assert target_commit_2 in recovered_commits
    assert random_commit not in recovered_commits


def test_commit_post_empty(db, client):
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
            "message": "The commit message",
            "ci_passed": False,
            "commitid": "commit_sha",
        },
        format="json",
    )
    response_json = response.json()
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["author", "commitid", "timestamp", "message", "repository"],
        )
    )
    assert response_json["repository"] == {
        "name": repository.name,
        "private": repository.private,
        "active": repository.active,
        "language": repository.language,
        "yaml": repository.yaml,
    }
    assert response_json["author"] is None  # This is filled by the worker
    assert response_json["commitid"] == "commit_sha"
