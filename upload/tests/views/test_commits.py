import pytest
from django.forms import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.models import Commit
from core.tests.factories import CommitFactory, RepositoryFactory
from upload.views.commits import CommitViews


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


def test_commits_get(client, db):
    repo = RepositoryFactory(name="the-repo")
    commit_1 = CommitFactory(repository=repo)
    commit_2 = CommitFactory(repository=repo)
    # Some other commit in the DB that doens't belong to repo
    # It should not be returned in the response
    CommitFactory()
    url = reverse("new_upload.commits", args=[repo.name])
    assert url == f"/upload/{repo.name}/commits"
    res = client.get(url)
    assert res.status_code == 200
    content = res.json()
    assert content.get("count") == 2
    # Test that we get the correct commits back, regardless of order
    assert content.get("results")[0].get("commitid") in [
        commit_1.commitid,
        commit_2.commitid,
    ]
    assert content.get("results")[1].get("commitid") in [
        commit_1.commitid,
        commit_2.commitid,
    ]
    assert content.get("results")[0].get("commitid") != content.get("results")[1].get(
        "commitid"
    )


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
        {"commitid": "commit_sha", "pullid": "4", "branch": "abc"},
        format="json",
    )
    response_json = response.json()
    commit = Commit.objects.get(commitid="commit_sha")
    expected_response = {
        "author": None,
        "branch": "abc",
        "ci_passed": None,
        "commitid": "commit_sha",
        "message": None,
        "parent_commit_id": None,
        "repository": {
            "name": repository.name,
            "is_private": repository.private,
            "active": repository.active,
            "language": repository.language,
            "yaml": repository.yaml,
        },
        "pullid": 4,
        "state": None,
        "timestamp": commit.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    assert response.status_code == 201
    assert expected_response == response_json
