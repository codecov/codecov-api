from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient
from shared.yaml.user_yaml import UserYaml

from core.tests.factories import CommitFactory, RepositoryFactory
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
    response = client.post(
        url,
    )
    response_json = response.json()
    assert response.status_code == 200
    assert (
        response_json.get("result")
        == "All changed files are ignored. Triggering passing notifications."
    )
    notify_mock.assert_called_once_with(
        repoid=repository.repoid, commitid=commit.commitid, empty_upload="pass"
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
        ["README.md", "codecov.yml", "template.txt"]
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
