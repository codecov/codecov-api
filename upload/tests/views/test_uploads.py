import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from codecov_auth.authentication.repo_auth import OrgLevelTokenRepositoryAuth
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from codecov_auth.tests.factories import OrganizationLevelTokenFactory, OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import (
    CommitReport,
    ReportSession,
    RepositoryFlag,
    UploadFlagMembership,
)
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.views.uploads import CanDoCoverageUploadsPermission, UploadViews


def test_upload_permission_class_pass(db, mocker):
    request_mocked = MagicMock(auth=MagicMock())
    request_mocked.auth.get_scopes.return_value = ["upload"]
    permission = CanDoCoverageUploadsPermission()
    assert permission.has_permission(request_mocked, MagicMock())
    request_mocked.auth.get_scopes.assert_called_once()


def test_upload_permission_orglevel_token(db, mocker):
    owner = OwnerFactory(plan="users-enterprisem")
    owner.save()
    repo = RepositoryFactory(author=owner)
    repo.save()
    token = OrgLevelTokenService.get_or_create_org_token(owner)

    request_mocked = MagicMock(auth=OrgLevelTokenRepositoryAuth(token))
    mocked_view = MagicMock()
    mocked_view.get_repo = MagicMock(return_value=repo)
    permission = CanDoCoverageUploadsPermission()
    assert permission.has_permission(request_mocked, mocked_view)
    mocked_view.get_repo.assert_called_once()


def test_upload_permission_class_fail(db, mocker):
    request_mocked = MagicMock(auth=MagicMock())
    request_mocked.auth.get_scopes.return_value = ["wrong_scope"]
    permission = CanDoCoverageUploadsPermission()
    assert not permission.has_permission(request_mocked, MagicMock())
    request_mocked.auth.get_scopes.assert_called_once()


def test_upload_permission_orglevel_fail(db, mocker):
    owner = OwnerFactory(plan="users-enterprisem")
    owner.save()
    repo = RepositoryFactory()  # Not the same owner of the token
    repo.save()
    token = OrgLevelTokenService.get_or_create_org_token(owner)

    request_mocked = MagicMock(auth=OrgLevelTokenRepositoryAuth(token))
    mocked_view = MagicMock()
    mocked_view.get_repo = MagicMock(return_value=repo)
    permission = CanDoCoverageUploadsPermission()
    assert not permission.has_permission(request_mocked, mocked_view)
    mocked_view.get_repo.assert_called_once()


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
        args=["github", "codecov::::the-repo", "commit-sha", "report-code"],
    )
    assert (
        url
        == "/upload/github/codecov::::the-repo/commits/commit-sha/reports/report-code/uploads"
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


@patch("shared.metrics.metrics.incr")
def test_get_repo_not_found(mock_metrics, db):
    upload_views = UploadViews()
    upload_views.kwargs = dict(repo="repo", service="github")
    with pytest.raises(ValidationError) as exp:
        upload_views.get_repo()
    assert exp.match("Repository not found")
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
        repo=repository.name, commit_sha=commit.commitid, report_code=report.code
    )
    recovered_report = upload_views.get_report(commit)
    assert recovered_report == report


def test_get_default_report(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    report = CommitReport(commit=commit)
    repository.save()
    commit.save()
    report.save()
    upload_views = UploadViews()
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, report_code="default"
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
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, report_code="random_code"
    )
    with pytest.raises(ValidationError) as exp:
        upload_views.get_report(commit)
        mock_metrics.assert_called_once_with("uploads.rejected", 1)
    assert exp.match("Report not found")


@patch("shared.metrics.metrics.incr")
def test_uploads_post(mock_metrics, db, mocker, mock_redis):
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
    commit_report = CommitReport.objects.create(commit=commit, code="code")
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
            commit_report.code,
        ],
    )
    response = client.post(
        url,
        {"state": "uploaded", "flags": ["flag1", "flag2"]},
    )
    response_json = response.json()
    upload = ReportSession.objects.filter(
        report_id=commit_report.id, upload_extras={"format_version": "v1"}
    ).first()
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["external_id", "created_at", "raw_upload_location"],
        )
    )
    assert ReportSession.objects.filter(
        report_id=commit_report.id, upload_extras={"format_version": "v1"}
    ).exists()
    assert RepositoryFlag.objects.filter(
        repository_id=repository.repoid, flag_name="flag1"
    ).exists()
    assert RepositoryFlag.objects.filter(
        repository_id=repository.repoid, flag_name="flag2"
    ).exists()
    flag1 = RepositoryFlag.objects.filter(
        repository_id=repository.repoid, flag_name="flag1"
    ).first()
    flag2 = RepositoryFlag.objects.filter(
        repository_id=repository.repoid, flag_name="flag2"
    ).first()
    assert UploadFlagMembership.objects.filter(
        report_session_id=upload.id, flag_id=flag1.id
    ).exists()
    assert UploadFlagMembership.objects.filter(
        report_session_id=upload.id, flag_id=flag2.id
    ).exists()
    assert [flag for flag in upload.flags.all()] == [flag1, flag2]
    mock_metrics.assert_called_once_with("uploads.accepted", 1)
    presigned_put_mock.assert_called()
    upload_task_mock.assert_called()


def test_deactivated_repo(db, mocker, mock_redis):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        active=True,
        activated=False,
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")
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
            commit_report.code,
        ],
    )
    response = client.post(
        url,
        {"state": "uploaded"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json == [
        f"This repository has been deactivated. To resume uploading to it, please activate the repository in the codecov UI: {settings.CODECOV_DASHBOARD_URL}/github/codecov/the_repo/settings"
    ]


def test_trigger_upload_task(db, mocker):
    upload_views = UploadViews()
    repo = RepositoryFactory.create()
    upload = UploadFactory.create()
    report = CommitReportFactory.create()
    commitid = "commit id"
    mocked_redis = mocker.patch("upload.views.uploads.get_redis_connection")
    mocked_dispatched_task = mocker.patch("upload.views.uploads.dispatch_upload_task")
    upload_views.trigger_upload_task(repo, commitid, upload, report)
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
