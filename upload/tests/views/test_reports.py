from django.urls import reverse
from rest_framework.test import APIClient

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport, ReportResults
from reports.tests.factories import ReportResultsFactory
from upload.views.uploads import CanDoCoverageUploadsPermission


def test_reports_get_not_allowed(client, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    url = reverse("new_upload.reports", args=["service", "the-repo", "commit-sha"])
    assert url == "/upload/service/the-repo/commits/commit-sha/reports"
    res = client.get(url)
    assert res.status_code == 405


def test_reports_post(client, db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(url, data={"code": "code1"})

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(commit_id=commit.id, code="code1").exists()


def test_create_report_already_exists(client, db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    report = CommitReport.objects.create(commit=commit, code="code")

    repository.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(url, data={"code": "code"})

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(commit_id=commit.id, code="code").exists()


def test_reports_post_code_as_default(client, db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    repository.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(url, data={"code": "default"})

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(commit_id=commit.id, code=None).exists()


def test_reports_results_post_successful(client, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
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
        "new_upload.reports_results",
        args=["github", "codecov::::the_repo", commit.commitid, "code"],
    )
    response = client.post(url, content_type="application/json", data={})

    assert (
        url
        == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports/code/results"
    )
    assert response.status_code == 201
    assert ReportResults.objects.filter(
        report_id=commit_report.id,
    ).exists()


def test_report_results_get_successful(client, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    commit_report_results = ReportResultsFactory(report=commit_report)
    repository.save()
    commit_report_results.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.reports_results",
        args=["github", "codecov::::the_repo", commit.commitid, "code"],
    )
    response = client.get(url, content_type="application/json", data={})

    assert (
        url
        == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports/code/results"
    )
    assert response.status_code == 200
    assert response.json() == {
        "external_id": str(commit_report_results.external_id),
        "report": {
            "external_id": str(commit_report.external_id),
            "created_at": commit_report.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "commit_sha": commit_report.commit.commitid,
            "code": commit_report.code,
        },
        "state": commit_report_results.state,
        "result": {},
        "completed_at": None,
    }


def test_report_results_get_unsuccessful(client, db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    repository.save()

    client = APIClient()
    client.force_authenticate(user=OwnerFactory())
    url = reverse(
        "new_upload.reports_results",
        args=["github", "codecov::::the_repo", commit.commitid, "code"],
    )
    response = client.get(url, content_type="application/json", data={})

    assert (
        url
        == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports/code/results"
    )
    assert response.status_code == 400
    assert response.json() == ["Report Results not found"]
