import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport
from reports.tests.factories import UploadFactory
from upload.views.uploads import CanDoCoverageUploadsPermission, UploadViews


def test_upload_permission_class_pass(db, mocker):
    request_mocked = MagicMock(auth=MagicMock())
    request_mocked.auth.get_scopes.return_value = ["upload"]
    permission = CanDoCoverageUploadsPermission()
    assert permission.has_permission(request_mocked, MagicMock())
    request_mocked.auth.get_scopes.assert_called_once()


def test_upload_permission_class_fail(db, mocker):
    request_mocked = MagicMock(auth=MagicMock())
    request_mocked.auth.get_scopes.return_value = ["wrong_scope"]
    permission = CanDoCoverageUploadsPermission()
    assert not permission.has_permission(request_mocked, MagicMock())
    request_mocked.auth.get_scopes.assert_called_once()


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
        "new_upload.uploads",
        args=["github", "codecov::::the-repo", "commit-sha", "report-id"],
    )
    assert (
        url
        == "/upload/github/codecov::::the-repo/commits/commit-sha/reports/report-id/uploads"
    )
    res = client.get(url)
    assert res.status_code == 405


def test_get_repo(db):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    repository.save()
    upload_views = UploadViews()
    upload_views.kwargs = dict(repo="codecov::::the_repo", service="github")
    recovered_repo = upload_views.get_repo()
    assert recovered_repo == repository


@patch("shared.metrics.metrics.incr")
def test_get_repo_with_invalid_service(mock_metrics, db):
    upload_views = UploadViews()
    upload_views.kwargs = dict(repo="repo", service="wrong service")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_repo()
    assert exp.match("Service not found: wrong service")
    mock_metrics.assert_called_once_with("uploads.rejected", 1)


def test_get_commit(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    upload_views = UploadViews()
    upload_views.kwargs = dict(repo=repository.name, commit_sha=commit.commitid)
    recovered_commit = upload_views.get_commit(repository)
    assert recovered_commit == commit


@patch("shared.metrics.metrics.incr")
def test_get_commit_error(mock_metrics, db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    repository.save()
    upload_views = UploadViews()
    upload_views.kwargs = dict(repo=repository.name, commit_sha="missing_commit")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_commit(repository)
    assert exp.match("Commit SHA not found")
    mock_metrics.assert_called_once_with("uploads.rejected", 1)


def test_get_report(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    report = CommitReport(commit=commit)
    repository.save()
    commit.save()
    report.save()
    upload_views = UploadViews()
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, reportid=report.external_id
    )
    recovered_report = upload_views.get_report(commit)
    assert recovered_report == report


@patch("shared.metrics.metrics.incr")
def test_get_report_error(mock_metrics, db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    upload_views = UploadViews()
    report_uuid = uuid.uuid4()
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, reportid=report_uuid
    )
    with pytest.raises(ValidationError) as exp:
        upload_views.get_report(commit)
        mock_metrics.assert_called_once_with("uploads.rejected", 1)
    assert exp.match("Report not found")


@patch("shared.metrics.metrics.incr")
def test_uploads_post_empty(mock_metrics, db, mocker, mock_redis):
    # TODO remove the mock object and test the flow with the permissions
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    presigned_put_mock = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload_task_mock = mocker.patch(
        "upload.views.uploads.UploadViews.trigger_upload_task", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit)
    repository.save()
    commit_report.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.uploads",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
            commit_report.external_id,
        ],
    )
    response = client.post(
        url,
        {"state": "uploaded"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["external_id", "created_at", "raw_upload_location"],
        )
    )
    mock_metrics.assert_called_once_with("uploads.accepted", 1)
    presigned_put_mock.assert_called()
    upload_task_mock.assert_called()


def test_trigger_upload_task(db, mocker):
    upload_views = UploadViews()
    repo = RepositoryFactory.create()
    upload = UploadFactory.create()
    commitid = "commit id"
    mocked_redis = mocker.patch("upload.views.uploads.get_redis_connection")
    mocked_dispatched_task = mocker.patch("upload.views.uploads.dispatch_upload_task")
    upload_views.trigger_upload_task(repo, commitid, upload)
    mocked_redis.assert_called()
    mocked_dispatched_task.assert_called()


def test_activate_repo(db):
    repo = RepositoryFactory(active=False, deleted=True, activated=False)
    upload_views = UploadViews()
    upload_views.activate_repo(repo)
    assert repo.active
    assert repo.activated
    assert not repo.deleted


def test_activate_already_activated_repo(db):
    repo = RepositoryFactory(active=True, activated=True, deleted=False)
    upload_views = UploadViews()
    upload_views.activate_repo(repo)
    assert repo.active
