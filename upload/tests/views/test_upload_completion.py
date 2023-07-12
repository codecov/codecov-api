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
    assert (
        response_json.get("result")
        == f"Couldn't find any uploads for your commit {commit.commitid[:7]}"
    )


def test_upload_completion_view_processed_uploads(db, mocker):
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
    assert (
        response_json.get("result")
        == "All uploads got processed successfully. Triggering notifications now"
    )


def test_upload_completion_view_still_processing_uploads(db, mocker):
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
    assert (
        response_json.get("result")
        == "1 out of 2 uploads are still being in process. We'll be sending you notifications once your uploads finish processing."
    )


def test_upload_completion_view_errored_uploads(db, mocker):
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
    assert (
        response_json.get("result")
        == "1 out of 2 uploads did not get processed successfully. Sending notifications based on the processed uploads."
    )


def test_upload_completion_view_errored_and_processing_uploads(db, mocker):
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
    assert (
        response_json.get("result")
        == "1 out of 2 uploads did not get processed successfully, 1 out of 2 uploads are still being in process, we'll be sending you notifications once your uploads finish processing and based on the successfully processed ones."
    )
