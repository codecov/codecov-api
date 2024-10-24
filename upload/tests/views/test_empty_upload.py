from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
)
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory
from shared.yaml.user_yaml import UserYaml

from upload.views.uploads import CanDoCoverageUploadsPermission


class MockedProviderAdapter:
    def __init__(self, changed_files) -> None:
        self.changed_files = changed_files

    async def find_pull_request(self, commit):
        # Random value
        return "5"

    async def get_pull_request_files(self, pull_id):
        return self.changed_files


def test_uploads_get_not_allowed(client, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the-repo", author__username="codecov", author__service="github"
    )
    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=["github", "codecov::::the-repo", "commit-sha"],
    )
    assert url == "/upload/github/codecov::::the-repo/commits/commit-sha/empty-upload"
    res = client.get(url)
    assert res.status_code == 405


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_with_yaml_ignored_files(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_prometheus_metrics = mocker.patch("upload.metrics.API_UPLOAD_COUNTER.labels")
    mock_final_yaml.return_value = UserYaml(
        {
            "ignore": [
                "file.py",
                "another_file.py",
            ]
        }
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        [
            "file.py",
        ]
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(url, headers={"User-Agent": "codecov-cli/0.4.7"})
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )
    mock_prometheus_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "empty_upload",
            "repo_visibility": "private",
            "is_using_shelter": "no",
            "position": "end",
            "upload_version": None,
        },
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_non_testable_files(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {
            "ignore": [
                "file.py",
                "another_file.py",
            ]
        }
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        [
            "README.md",
            "codecov.yml",
            "template.txt",
            "dir/sub-dir/codecov.yml",
            ".circleci/config.yml",
        ]
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    assert response_json.get("non_ignored_files") == []
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_with_testable_file(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {"ignore": ["file.py", "another_file.py", "README.md"]}
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        ["README.md", "codecov.yml", "template.txt", "base.py"]
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "Some files cannot be ignored. Triggering failing notifications."
    )
    assert response_json.get("non_ignored_files") == ["base.py"]
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="fail"
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_with_testable_file_with_force(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {"ignore": ["file.py", "another_file.py", "README.md"]}
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        ["README.md", "codecov.yml", "template.txt", "base.py"]
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(url, data={"should_force": True})
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "Force option was enabled. Triggering passing notifications."
    )
    assert response_json.get("non_ignored_files") == []
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_with_testable_file_invalid_serializer(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {"ignore": ["file.py", "another_file.py", "README.md"]}
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        ["README.md", "codecov.yml", "template.txt", "base.py"]
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(url, data={"should_force": "hello world"})
    assert response.status_code == 400


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_no_changed_files_in_pr(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {
            "ignore": [
                "file.py",
                "another_file.py",
            ]
        }
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter([])
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    assert response_json.get("non_ignored_files") == []
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_empty_upload_no_changed_files_in_pr_github_oidc_auth(
    mock_jwks_client,
    mock_jwt_decode,
    mock_repo_provider_service,
    mock_final_yaml,
    notify_mock,
    db,
    mocker,
):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    mock_jwt_decode.return_value = {
        "repository": f"url/{repository.name}",
        "repository_owner": repository.author.username,
        "iss": "https://token.actions.githubusercontent.com",
    }
    token = "ThisValueDoesNotMatterBecauseOf_mock_jwt_decode"
    mock_final_yaml.return_value = UserYaml(
        {
            "ignore": [
                "file.py",
                "another_file.py",
            ]
        }
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter([])

    client = APIClient()
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
        headers={"Authorization": f"token {token}"},
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    assert response_json.get("non_ignored_files") == []
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )


@patch("services.task.TaskService.notify")
@patch("upload.views.empty_upload.final_commit_yaml")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_no_commit_pr_id(
    mock_repo_provider_service, mock_final_yaml, notify_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_final_yaml.return_value = UserYaml(
        {
            "ignore": [
                "file.py",
                "another_file.py",
            ]
        }
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter([])
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository, pullid=None)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    assert response_json.get("non_ignored_files") == []
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
    )


def test_empty_upload_no_auth(db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    token = "BAD"
    client = APIClient()
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
        headers={"Authorization": f"token {token}"},
    )
    response_json = response.json()
    assert response.status_code == 401
    assert (
        response_json.get("detail")
        == "Failed token authentication, please double-check that your repository token matches in the Codecov UI, "
        "or review the docs https://docs.codecov.com/docs/adding-the-codecov-token"
    )


@patch("services.yaml.fetch_commit_yaml")
@patch("services.task.TaskService.notify")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_commit_yaml_org_token(
    mock_repo_provider_service, notify_mock, fetch_yaml_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        ["README.md", "codecov.yml", "template.txt", "base.py"]
    )
    fetch_yaml_mock.return_value = None

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    org_token = OrganizationLevelTokenFactory.create(owner=repository.author)
    repository.save()
    commit.save()
    org_token.save()

    client = APIClient()
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
        headers={"Authorization": f"token {org_token.token}"},
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "Some files cannot be ignored. Triggering failing notifications."
    )
    assert response_json.get("non_ignored_files") == ["base.py"]
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="fail"
    )

    fetch_yaml_mock.assert_called_once_with(commit, repository.author)


@patch("services.yaml.fetch_commit_yaml")
@patch("services.task.TaskService.notify")
@patch("services.repo_providers.RepoProviderService.get_adapter")
def test_empty_upload_ommit_yaml_repo_token(
    mock_repo_provider_service, notify_mock, fetch_yaml_mock, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_repo_provider_service.return_value = MockedProviderAdapter(
        ["README.md", "codecov.yml", "template.txt", "base.py"]
    )
    fetch_yaml_mock.return_value = None

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    client = APIClient()
    url = reverse(
        "new_upload.empty_upload",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
        headers={"Authorization": f"token {repository.upload_token}"},
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "Some files cannot be ignored. Triggering failing notifications."
    )
    assert response_json.get("non_ignored_files") == ["base.py"]
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="fail"
    )

    fetch_yaml_mock.assert_called_once_with(commit, repository.author)
