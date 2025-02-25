from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from shared.api_archive.archive import ArchiveService, MinioEndpoints
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from billing.helpers import mock_all_plans_and_tiers
from reports.models import ReportSession, RepositoryFlag, UploadFlagMembership
from upload.views.upload_coverage import CanDoCoverageUploadsPermission


def test_get_repo(db):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    repository.save()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    response = client.post(url, {}, format="json")
    assert response.status_code == 400  # Bad request due to missing required fields
    assert "commitid" in response.json()


@patch("services.task.TaskService.upload")
def test_get_repo_not_found(upload, db):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    repo_slug = "codecov::::wrong-repo-name"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )
    client = APIClient()
    response = client.post(url, {}, format="json")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not valid tokenless upload"}
    assert not upload.called


def test_deactivated_repo(db):
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        active=True,
        activated=False,
    )
    repository.save()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    response = client.post(url, {"commitid": "abc123"}, format="json")
    assert response.status_code == 400
    assert "This repository is deactivated" in str(response.json())


def test_upload_coverage_with_errors(db):
    mock_all_plans_and_tiers()
    repository = RepositoryFactory()
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)

    # Missing required fields
    response = client.post(url, {}, format="json")
    assert response.status_code == 400
    assert "commitid" in response.json()

    # Invalid flag format
    response = client.post(
        url, {"commitid": "abc123", "flags": "not-a-list"}, format="json"
    )
    assert response.status_code == 400
    assert "flags" in response.json()


def test_upload_coverage_post(db, mocker):
    mock_all_plans_and_tiers()
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    presigned_put_mock = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload_task_mock = mocker.patch(
        "upload.views.uploads.trigger_upload_task", return_value=True
    )

    repository = RepositoryFactory(
        name="the_repo1", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {
            "branch": "branch",
            "ci_service": "ci_service",
            "ci_url": "ci_url",
            "code": "code",
            "commitid": commit.commitid,
            "flags": ["flag1", "flag2"],
            "job_code": "job_code",
            "version": "version",
        },
        format="json",
    )
    response_json = response.json()
    upload = ReportSession.objects.filter(
        report__commit=commit,
        report__code="code",
        upload_extras={"format_version": "v1"},
    ).first()
    assert response.status_code == 201
    assert all(
        (
            x in response_json.keys()
            for x in ["external_id", "created_at", "raw_upload_location", "url"]
        )
    )
    assert (
        response_json.get("url")
        == f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
    )

    assert ReportSession.objects.filter(
        report__commit=commit,
        report__code="code",
        upload_extras={"format_version": "v1"},
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
    assert list(upload.flags.all()) == [flag1, flag2]

    archive_service = ArchiveService(repository)
    assert upload.storage_path == MinioEndpoints.raw_with_upload_id.get_path(
        version="v4",
        date=upload.created_at.strftime("%Y-%m-%d"),
        repo_hash=archive_service.storage_hash,
        commit_sha=commit.commitid,
        reportid=upload.report.external_id,
        uploadid=upload.external_id,
    )
    presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)
    upload_task_mock.assert_called()


@override_settings(SHELTER_SHARED_SECRET="shelter-shared-secret")
def test_upload_coverage_post_shelter(db, mocker):
    mock_all_plans_and_tiers()
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    presigned_put_mock = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload_task_mock = mocker.patch(
        "upload.views.uploads.trigger_upload_task", return_value=True
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
    repo_slug = f"{repository.author.username}::::{repository.name}"
    url = reverse(
        "new_upload.upload_coverage",
        args=[repository.author.service, repo_slug],
    )
    response = client.post(
        url,
        {
            "branch": "branch",
            "ci_service": "ci_service",
            "ci_url": "ci_url",
            "code": "code",
            "commitid": commit.commitid,
            "flags": ["flag1", "flag2"],
            "job_code": "job_code",
            "storage_path": "shelter/test/path.txt",
            "version": "version",
        },
        headers={
            "X-Shelter-Token": "shelter-shared-secret",
            "User-Agent": "codecov-cli/0.4.7",
        },
        format="json",
    )
    response_json = response.json()
    upload = ReportSession.objects.filter(
        report__commit=commit,
        report__code="code",
        upload_extras={"format_version": "v1"},
    ).first()
    assert response.status_code == 201
    assert all(
        (
            x in response_json.keys()
            for x in ["external_id", "created_at", "raw_upload_location", "url"]
        )
    )
    assert (
        response_json.get("url")
        == f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
    )

    assert ReportSession.objects.filter(
        report__commit=commit,
        report__code="code",
        upload_extras={"format_version": "v1"},
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
    assert list(upload.flags.all()) == [flag1, flag2]

    assert upload.storage_path == "shelter/test/path.txt"
    presigned_put_mock.assert_called_with("archive", upload.storage_path, 10)
    upload_task_mock.assert_called()
