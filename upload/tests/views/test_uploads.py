from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from codecov_auth.authentication.repo_auth import OrgLevelTokenRepositoryAuth
from codecov_auth.services.org_level_token_service import OrgLevelTokenService
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.types.enums import UploadState
from reports.models import (
    CommitReport,
    ReportSession,
    RepositoryFlag,
    UploadFlagMembership,
)
from reports.tests.factories import CommitReportFactory, UploadFactory
from services.archive import ArchiveService, MinioEndpoints
from services.repo_providers import RepoProviderService
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
    CommitFactory(repository=repository, commitid="commit-sha")
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
        {
            # "state": "uploaded",
            "flags": ["flag1", "flag2"],
            "version": "version",
            # this cannot be passed in by default
            "storage_path": "this/path/should/be/ingored.txt",
        },
    )
    response_json = response.json()
    upload = ReportSession.objects.filter(
        report_id=commit_report.id,
        upload_extras={"format_version": "v1"},
        state=UploadState.UPLOADED.value,
    ).first()
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["external_id", "created_at", "raw_upload_location", "url"],
        )
    )
    assert (
        response_json.get("url")
        == f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
    )

    assert ReportSession.objects.filter(
        report_id=commit_report.id,
        upload_extras={"format_version": "v1"},
        state=UploadState.UPLOADED.value,
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
    mock_metrics.assert_has_calls(
        [call("upload.cli.version"), call("uploads.accepted", 1)]
    )

    archive_service = ArchiveService(repository)
    assert upload.storage_path == MinioEndpoints.raw_with_upload_id.get_path(
        version="v4",
        date=upload.created_at.strftime("%Y-%m-%d"),
        repo_hash=archive_service.storage_hash,
        commit_sha=commit.commitid,
        reportid=commit_report.external_id,
        uploadid=upload.external_id,
    )
    presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)
    upload_task_mock.assert_called()


@patch("shared.metrics.metrics.incr")
@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("branch", ["branch", "fork:branch", "someone/fork:branch"])
@pytest.mark.parametrize(
    "branch_sent", [None, "branch", "fork:branch", "someone/fork:branch"]
)
def test_uploads_post_tokenless(
    mock_metrics, db, mocker, mock_redis, private, branch, branch_sent
):
    presigned_put_mock = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload_task_mock = mocker.patch(
        "upload.views.uploads.UploadViews.trigger_upload_task", return_value=True
    )
    analytics_service_mock = mocker.patch("upload.views.uploads.AnalyticsService")

    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=private,
    )
    commit = CommitFactory(repository=repository)
    commit.branch = branch
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    repository.save()
    commit_report.save()
    commit.save()

    client = APIClient()
    url = reverse(
        "new_upload.uploads",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
            commit_report.code,
        ],
    )
    if branch_sent is not None:
        data = {
            # "state": "uploaded",
            "flags": ["flag1", "flag2"],
            "version": "version",
            "branch": branch_sent,
        }
    else:
        data = {
            # "state": "uploaded",
            "flags": ["flag1", "flag2"],
            "version": "version",
        }
    response = client.post(
        url,
        data,
    )

    if private is False and ":" in branch:
        assert response.status_code == 201
        response_json = response.json()
        upload = ReportSession.objects.filter(
            report_id=commit_report.id,
            upload_extras={"format_version": "v1"},
            state=UploadState.UPLOADED.value,
        ).first()
        assert all(
            map(
                lambda x: x in response_json.keys(),
                ["external_id", "created_at", "raw_upload_location", "url"],
            )
        )
        assert (
            response_json.get("url")
            == f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
        )

        assert ReportSession.objects.filter(
            report_id=commit_report.id,
            upload_extras={"format_version": "v1"},
            state=UploadState.UPLOADED.value,
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
        mock_metrics.assert_has_calls(
            [call("upload.cli.version"), call("uploads.accepted", 1)]
        )

        archive_service = ArchiveService(repository)
        assert upload.storage_path == MinioEndpoints.raw_with_upload_id.get_path(
            version="v4",
            date=upload.created_at.strftime("%Y-%m-%d"),
            repo_hash=archive_service.storage_hash,
            commit_sha=commit.commitid,
            reportid=commit_report.external_id,
            uploadid=upload.external_id,
        )
        presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)
        upload_task_mock.assert_called()
        analytics_service_mock.return_value.account_uploaded_coverage_report.assert_called_with(
            commit.repository.author.ownerid,
            {
                "commit": commit.commitid,
                "branch": commit.branch,
                "pr": commit.pullid,
                "repo": commit.repository.name,
                "repository_name": commit.repository.name,
                "repository_id": commit.repository.repoid,
                "service": commit.repository.service,
                "build": upload.build_code,
                "build_url": upload.build_url,
                "flags": "",
                "owner": commit.repository.author.ownerid,
                "token": "tokenless_upload",
                "version": "version",
                "uploader_type": "CLI",
            },
        )
    else:
        assert response.status_code == 401
        assert response.json().get("detail") == "Not valid tokenless upload"


@patch("upload.views.uploads.AnalyticsService")
@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
@patch("shared.metrics.metrics.incr")
def test_uploads_post_github_oidc_auth(
    mock_metrics,
    mock_jwks_client,
    mock_jwt_decode,
    analytics_service_mock,
    db,
    mocker,
    mock_redis,
):
    presigned_put_mock = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload_task_mock = mocker.patch(
        "upload.views.uploads.UploadViews.trigger_upload_task", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=False,
    )
    mock_jwt_decode.return_value = {
        "repository": f"url/{repository.name}",
        "repository_owner": repository.author.username,
        "iss": "https://token.actions.githubusercontent.com",
        "audience": [settings.CODECOV_API_URL],
    }
    token = "ThisValueDoesNotMatterBecauseOf_mock_jwt_decode"

    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")

    client = APIClient()
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
        {
            # "state": "uploaded",
            "flags": ["flag1", "flag2"],
            "version": "version",
        },
        headers={"Authorization": f"token {token}"},
    )
    assert response.status_code == 201
    response_json = response.json()
    upload = ReportSession.objects.filter(
        report_id=commit_report.id,
        upload_extras={"format_version": "v1"},
        state=UploadState.UPLOADED.value,
    ).first()
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["external_id", "created_at", "raw_upload_location", "url"],
        )
    )
    assert (
        response_json.get("url")
        == f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
    )

    assert ReportSession.objects.filter(
        report_id=commit_report.id,
        upload_extras={"format_version": "v1"},
        state=UploadState.UPLOADED.value,
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
    mock_metrics.assert_has_calls(
        [call("upload.cli.version"), call("uploads.accepted", 1)]
    )

    archive_service = ArchiveService(repository)
    assert upload.storage_path == MinioEndpoints.raw_with_upload_id.get_path(
        version="v4",
        date=upload.created_at.strftime("%Y-%m-%d"),
        repo_hash=archive_service.storage_hash,
        commit_sha=commit.commitid,
        reportid=commit_report.external_id,
        uploadid=upload.external_id,
    )
    presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)
    upload_task_mock.assert_called()
    analytics_service_mock.return_value.account_uploaded_coverage_report.assert_called_with(
        commit.repository.author.ownerid,
        {
            "commit": commit.commitid,
            "branch": commit.branch,
            "pr": commit.pullid,
            "repo": commit.repository.name,
            "repository_name": commit.repository.name,
            "repository_id": commit.repository.repoid,
            "service": commit.repository.service,
            "build": upload.build_code,
            "build_url": upload.build_url,
            "flags": "",
            "owner": commit.repository.author.ownerid,
            "token": "oidc_token_upload",
            "version": "version",
            "uploader_type": "CLI",
        },
    )


@override_settings(SHELTER_SHARED_SECRET="shelter-shared-secret")
def test_uploads_post_shelter(db, mocker, mock_redis):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    presigned_put_mock = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    mocker.patch(
        "upload.views.uploads.UploadViews.trigger_upload_task", return_value=True
    )
    mock_sentry_metrics = mocker.patch("upload.views.uploads.sentry_metrics.incr")
    mock_sentry_metrics_set = mocker.patch("upload.views.uploads.sentry_metrics.set")

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
        {
            # "state": "uploaded",
            "flags": ["flag1", "flag2"],
            "version": "version",
            "storage_path": "shelter/test/path.txt",
        },
        headers={
            "X-Shelter-Token": "shelter-shared-secret",
            "User-Agent": "codecov-cli/0.4.7",
        },
    )

    mock_sentry_metrics.assert_called_with(
        "upload",
        tags={
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_upload",
            "repo_visibility": "private",
            "is_using_shelter": "yes",
        },
    )

    mock_sentry_metrics_set.assert_called_with(
        "upload_set",
        owner.ownerid,
        tags={
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_upload",
            "repo_visibility": "private",
            "is_using_shelter": "yes",
        },
    )

    upload = ReportSession.objects.filter(
        report_id=commit_report.id, upload_extras={"format_version": "v1"}
    ).first()
    assert response.status_code == 201
    ArchiveService(repository)
    assert upload.storage_path == "shelter/test/path.txt"
    presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)


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
        {
            # "state": "uploaded"
        },
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
    repo = RepositoryFactory(
        active=False, deleted=True, activated=False, coverage_enabled=False
    )
    upload_views = UploadViews()
    upload_views.activate_repo(repo)
    assert repo.active
    assert repo.activated
    assert not repo.deleted
    assert repo.coverage_enabled


def test_activate_already_activated_repo(db):
    repo = RepositoryFactory(
        active=True, activated=True, deleted=False, coverage_enabled=True
    )
    upload_views = UploadViews()
    upload_views.activate_repo(repo)
    assert repo.active
