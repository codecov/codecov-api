from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient

from core.tests.factories import CommitFactory, RepositoryFactory
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
