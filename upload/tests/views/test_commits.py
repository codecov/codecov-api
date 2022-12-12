import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.models import Commit
from core.tests.factories import CommitFactory, RepositoryFactory
from services.task import TaskService
from upload.views.commits import CommitViews


def test_get_repo(db):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    repository.save()
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="codecov::::the_repo", service="github")
    recovered_repo = upload_views.get_repo()
    assert recovered_repo == repository


def test_get_repo_with_invalid_service():
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="repo", service="wrong service")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_repo()
    assert exp.match("Service not found: wrong service")


def test_get_repo_not_found(db):
    # Making sure that owner has different repos and getting none when the name of the repo isn't correct
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="codecov::::wrong-repo-name", service="github")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_repo()
    assert exp.match("Repository not found")


def test_get_queryset(db):
    target_repo = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    random_repo = RepositoryFactory()
    target_commit_1 = CommitFactory(repository=target_repo)
    target_commit_2 = CommitFactory(repository=target_repo)
    random_commit = CommitFactory(repository=random_repo)
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="codecov::::the_repo", service="github")
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
    repo_slug = f"{repo.author.username}::::{repo.name}"
    url = reverse("new_upload.commits", args=[repo.author.service, repo_slug])
    assert url == f"/upload/{repo.author.service}/{repo_slug}/commits"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repo.upload_token)
    res = client.get(url, format="json")
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


def test_commit_post_empty(db, client, mocker):
    mocked_call = mocker.patch.object(TaskService, "update_commit")
    repository = RepositoryFactory.create()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.commits",
        args=[repository.author.service, repo_slug],
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
    mocked_call.assert_called_with(commitid="commit_sha", repoid=repository.repoid)
