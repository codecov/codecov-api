from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from core.models import Commit
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
    RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    upload_views = CommitViews()
    upload_views.kwargs = dict(repo="codecov::::wrong-repo-name", service="github")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_repo()
    assert exp.match("Repository not found")


def test_deactivated_repo(db):
    repo = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        active=True,
        activated=False,
    )
    repo.save()
    repo_slug = f"{repo.author.username}::::{repo.name}"

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repo.upload_token)
    url = reverse(
        "new_upload.commits",
        args=[repo.author.service, repo_slug],
    )
    response = client.post(
        url,
        {"commitid": "commit_sha"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json == [
        f"This repository is deactivated. To resume uploading to it, please activate the repository in the codecov UI: {settings.CODECOV_DASHBOARD_URL}/github/codecov/the_repo/config/general"
    ]


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


@pytest.mark.parametrize(
    "repo_privacy,status_code,detail",
    [
        (
            True,
            401,
            "Not valid tokenless upload",
        ),
        (
            False,
            200,
            None,
        ),
    ],
)
def test_commits_get_no_auth(client, db, repo_privacy, status_code, detail):
    repo = RepositoryFactory(name="the-repo")
    repo.private = repo_privacy
    repo.save()
    CommitFactory(repository=repo)
    CommitFactory(repository=repo)
    repo_slug = f"{repo.author.username}::::{repo.name}"
    url = reverse("new_upload.commits", args=[repo.author.service, repo_slug])
    assert url == f"/upload/{repo.author.service}/{repo_slug}/commits"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token BAD")
    res = client.get(url, format="json")
    assert res.status_code == status_code
    assert res.json().get("detail") == detail


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


def test_create_commit_already_exists(db, client, mocker):
    mocked_call = mocker.patch.object(TaskService, "update_commit")
    repository = RepositoryFactory.create()
    commit = CommitFactory(repository=repository, author=None)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.commits",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {"commitid": commit.commitid, "pullid": "4", "branch": "abc"},
        format="json",
    )
    response_json = response.json()
    expected_response = {
        "author": None,
        "branch": commit.branch,
        "ci_passed": commit.ci_passed,
        "commitid": commit.commitid,
        "message": commit.message,
        "parent_commit_id": commit.parent_commit_id,
        "repository": {
            "name": repository.name,
            "is_private": repository.private,
            "active": repository.active,
            "language": repository.language,
            "yaml": repository.yaml,
        },
        "pullid": commit.pullid,
        "state": commit.state,
        "timestamp": commit.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    assert response.status_code == 201
    assert expected_response == response_json
    mocked_call.assert_not_called()


@pytest.mark.parametrize("branch", ["main", "someone:main", "someone/fork:main"])
@pytest.mark.parametrize("private", [True, False])
def test_commit_tokenless(db, client, mocker, branch, private):
    repository = RepositoryFactory.create(
        private=private,
        author__username="codecov",
        name="the_repo",
        author__upload_token_required_for_public_repos=True,
    )
    mocked_call = mocker.patch.object(TaskService, "update_commit")

    client = APIClient()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.commits",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {
            "commitid": "commit_sha",
            "pullid": "4",
            "branch": branch,
        },
        format="json",
    )

    if ":" in branch and private == False:
        assert response.status_code == 201
        response_json = response.json()
        commit = Commit.objects.get(commitid="commit_sha")
        expected_response = {
            "author": None,
            "branch": f"{branch}",
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
        assert expected_response == response_json
        mocked_call.assert_called_with(commitid="commit_sha", repoid=repository.repoid)
    else:
        assert response.status_code == 401
        commit = Commit.objects.filter(commitid="commit_sha").first()
        assert commit is None


@pytest.mark.parametrize("branch", ["main", "someone:main", "someone/fork:main"])
@pytest.mark.parametrize("private", [True, False])
@pytest.mark.parametrize("upload_token_required_for_public_repos", [True, False])
def test_commit_upload_token_required_auth_check(
    db, client, mocker, branch, private, upload_token_required_for_public_repos
):
    repository = RepositoryFactory(
        private=private,
        author__username="codecov",
        name="the_repo",
        author__upload_token_required_for_public_repos=upload_token_required_for_public_repos,
    )
    mocked_call = mocker.patch.object(TaskService, "update_commit")

    client = APIClient()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.commits",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {
            "commitid": "commit_sha",
            "pullid": "4",
            "branch": branch,
        },
        format="json",
    )

    # when TokenlessAuthentication is removed, this test should use `if private == False and upload_token_required_for_public_repos == False:`
    # but TokenlessAuthentication lets some additional uploads through.
    authorized_by_tokenless_auth_class = ":" in branch

    if private == False and (
        upload_token_required_for_public_repos == False
        or authorized_by_tokenless_auth_class
    ):
        assert response.status_code == 201
        response_json = response.json()
        commit = Commit.objects.get(commitid="commit_sha")
        expected_response = {
            "author": None,
            "branch": f"{branch}",
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
        assert expected_response == response_json
        mocked_call.assert_called_with(commitid="commit_sha", repoid=repository.repoid)
    else:
        assert response.status_code == 401
        commit = Commit.objects.filter(commitid="commit_sha").first()
        assert commit is None


@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_commit_github_oidc_auth(mock_jwks_client, mock_jwt_decode, db, mocker):
    repository = RepositoryFactory.create(
        private=False, author__username="codecov", name="the_repo"
    )
    mocked_call = mocker.patch.object(TaskService, "update_commit")
    mock_prometheus_metrics = mocker.patch("upload.metrics.API_UPLOAD_COUNTER.labels")
    mock_jwt_decode.return_value = {
        "repository": f"url/{repository.name}",
        "repository_owner": repository.author.username,
        "iss": "https://token.actions.githubusercontent.com",
    }
    token = "ThisValueDoesNotMatterBecauseOf_mock_jwt_decode"

    client = APIClient()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.commits",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {
            "commitid": "commit_sha",
            "pullid": "4",
        },
        format="json",
        headers={"Authorization": f"token {token}", "User-Agent": "codecov-cli/0.4.7"},
    )
    assert response.status_code == 201
    response_json = response.json()
    commit = Commit.objects.get(commitid="commit_sha")
    expected_response = {
        "author": None,
        "branch": None,
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
    assert expected_response == response_json
    mocked_call.assert_called_with(commitid="commit_sha", repoid=repository.repoid)
    mock_prometheus_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_commit",
            "repo_visibility": "public",
            "is_using_shelter": "no",
            "position": "end",
            "upload_version": None,
        },
    )
