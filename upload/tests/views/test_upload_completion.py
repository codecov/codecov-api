from unittest.mock import patch

from django.http import HttpResponse
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.views.uploads import CanDoCoverageUploadsPermission


def test_upload_completion_view_no_uploads(db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
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
        "new_upload.upload-complete",
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
    assert response.status_code == 404
    assert response_json == {
        "uploads_total": 0,
        "uploads_success": 0,
        "uploads_processing": 0,
        "uploads_error": 0,
    }


@patch("services.task.TaskService.manual_upload_completion_trigger")
def test_upload_completion_view_processed_uploads(mocked_manual_trigger, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mock_prometheus_metrics = mocker.patch("upload.metrics.API_UPLOAD_COUNTER.labels")
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report)
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.upload-complete",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(url, headers={"User-Agent": "codecov-cli/0.4.7"})
    response_json = response.json()
    assert response.status_code == 200
    assert response_json == {
        "uploads_total": 2,
        "uploads_success": 2,
        "uploads_processing": 0,
        "uploads_error": 0,
    }
    mocked_manual_trigger.assert_called_once_with(repository.repoid, commit.commitid)
    mock_prometheus_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "upload_complete",
            "repo_visibility": "private",
            "is_using_shelter": "no",
            "position": "end",
            "upload_version": None,
        },
    )


@patch("services.task.TaskService.manual_upload_completion_trigger")
@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_upload_completion_view_processed_uploads_github_oidc_auth(
    mock_jwks_client, mock_jwt_decode, mocked_manual_trigger, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    mock_jwt_decode.return_value = {
        "repository": f"url/{repository.name}",
        "repository_owner": repository.author.username,
        "iss": "https://token.actions.githubusercontent.com",
    }
    token = "ThisValueDoesNotMatterBecauseOf_mock_jwt_decode"
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report)
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {token}")
    url = reverse(
        "new_upload.upload-complete",
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
    assert response_json == {
        "uploads_total": 2,
        "uploads_success": 2,
        "uploads_processing": 0,
        "uploads_error": 0,
    }
    mocked_manual_trigger.assert_called_once_with(repository.repoid, commit.commitid)


def test_upload_completion_view_no_auth(db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    token = "BAD"
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report)
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {token}")
    url = reverse(
        "new_upload.upload-complete",
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
    assert response.status_code == 401
    assert (
        response_json.get("detail")
        == "Failed token authentication, please double-check that your repository token matches in the Codecov UI, "
        "or review the docs https://docs.codecov.com/docs/adding-the-codecov-token"
    )


@patch("codecov_auth.authentication.repo_auth.exception_handler")
def test_upload_completion_view_repo_auth_custom_exception_handler_error(
    customized_error, db, mocker
):
    mocked_response = HttpResponse(
        "No content posted.",
        status=status.HTTP_401_UNAUTHORIZED,
        content_type="application/json",
    )
    mocked_response.data = "invalid"
    customized_error.return_value = mocked_response
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    token = "BAD"
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report)
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {token}")
    url = reverse(
        "new_upload.upload-complete",
        args=[
            "github",
            "codecov::::the_repo",
            commit.commitid,
        ],
    )
    response = client.post(
        url,
    )
    assert response.status_code == 401
    assert response == mocked_response


@patch("services.task.TaskService.manual_upload_completion_trigger")
def test_upload_completion_view_still_processing_uploads(
    mocked_manual_trigger, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report, state="")
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.upload-complete",
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
    assert response_json == {
        "uploads_total": 2,
        "uploads_success": 1,
        "uploads_processing": 1,
        "uploads_error": 0,
    }
    mocked_manual_trigger.assert_called_once_with(repository.repoid, commit.commitid)


@patch("services.task.TaskService.manual_upload_completion_trigger")
def test_upload_completion_view_errored_uploads(mocked_manual_trigger, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report)
    upload2 = UploadFactory(report=report, state="error")
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.upload-complete",
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
    assert response_json == {
        "uploads_total": 2,
        "uploads_success": 1,
        "uploads_processing": 0,
        "uploads_error": 1,
    }
    mocked_manual_trigger.assert_called_once_with(repository.repoid, commit.commitid)


@patch("services.task.TaskService.manual_upload_completion_trigger")
def test_upload_completion_view_errored_and_processing_uploads(
    mocked_manual_trigger, db, mocker
):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    report = CommitReportFactory(commit=commit)
    upload1 = UploadFactory(report=report, state="")
    upload2 = UploadFactory(report=report, state="error")
    repository.save()
    commit.save()
    report.save()
    upload1.save()
    upload2.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.upload-complete",
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
    assert response_json == {
        "uploads_total": 2,
        "uploads_success": 0,
        "uploads_processing": 1,
        "uploads_error": 1,
    }
    mocked_manual_trigger.assert_called_once_with(repository.repoid, commit.commitid)
