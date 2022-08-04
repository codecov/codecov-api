import pytest
from django.core.exceptions import PermissionDenied
from django.forms import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport, ReportSession
from services.task import TaskService
from upload.views.mutation_uploads import MutationTestUploadView


def test_mutation_upload(db, mocker):
    mocked_call = mocker.patch.object(TaskService, "mutation_test_upload")
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )

    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit)
    owner = OwnerFactory(plan=BASIC_PLAN_NAME)
    client = APIClient()
    client.force_authenticate(user=owner)

    url = reverse(
        "new_upload.mutation_uploads",
        args=[repository.name, commit.commitid, commit_report.id],
    )
    response = client.post(
        url, {"name": "report_name", "state": "uploaded"}, format="json"
    )
    assert response.status_code == 201
    response_json = response.json()
    assert all(
        map(
            lambda x: x in response_json.keys(),
            [
                "storage_path",
                "created_at",
                "external_id",
                "raw_upload_location",
            ],
        )
    )
    assert response_json["raw_upload_location"] == "presigned put"
    mocked_call.assert_called()


def test_mutation_upload_permission_denied_outside_codecov(db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="annonymous", author__name="Annonymus"
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit)
    number_of_commit_reports_before = ReportSession.objects.all().count()

    owner = OwnerFactory(plan=BASIC_PLAN_NAME)
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.mutation_uploads",
        args=[repository.name, commit.commitid, commit_report.id],
    )
    response = client.post(
        url, {"name": "report_name", "state": "uploaded"}, format="json"
    )
    assert response.status_code == 403
    # Assert a new ReportSession was not created
    assert number_of_commit_reports_before == ReportSession.objects.all().count()


def test_get_repo(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    repository.save()
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(repo=repository.name)
    recovered_repo = upload_views.get_repo()
    assert recovered_repo == repository


def test_get_repo_error(db):
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(repo="repo_missing")
    with pytest.raises(ValidationError):
        upload_views.get_repo()


def test_get_commit(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(repo=repository.name, commit_sha=commit.commitid)
    recovered_commit = upload_views.get_commit()
    assert recovered_commit == commit


def test_get_commit_error(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    repository.save()
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(repo=repository.name, commit_sha="missing_commit")
    with pytest.raises(ValidationError):
        upload_views.get_commit()


def test_get_report(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    report = CommitReport(commit=commit)
    repository.save()
    commit.save()
    report.save()
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, reportid=report.external_id
    )
    recovered_report = upload_views.get_report()
    assert recovered_report == report


def test_get_report_error(db):
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    repository.save()
    commit.save()
    upload_views = MutationTestUploadView()
    upload_views.kwargs = dict(
        repo=repository.name, commit_sha=commit.commitid, reportid="missing-report"
    )
    with pytest.raises(ValidationError):
        upload_views.get_report()
