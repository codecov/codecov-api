from unittest.mock import AsyncMock, MagicMock, patch

from django.urls import reverse
from rest_framework.test import APIClient

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport, ReportResults
from reports.tests.factories import ReportResultsFactory
from services.repo_providers import RepoProviderService
from services.task.task import TaskService
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
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    mock_sentry_metrics = mocker.patch("upload.views.reports.sentry_metrics.incr")
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
    response = client.post(
        url, data={"code": "code1"}, headers={"User-Agent": "codecov-cli/0.4.7"}
    )

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(
        commit_id=commit.id, code="code1", report_type=CommitReport.ReportType.COVERAGE
    ).exists()
    mocked_call.assert_called_with(repository.repoid, commit.commitid, "code1")
    mock_sentry_metrics.assert_called_with(
        "upload",
        tags={
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_report",
            "repo_visibility": "private",
            "is_using_shelter": "no",
        },
    )


@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_reports_post_github_oidc_auth(
    mock_jwks_client, mock_jwt_decode, client, db, mocker
):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
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
    repository.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + token)
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(url, data={"code": "code1"})

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(
        commit_id=commit.id, code="code1", report_type=CommitReport.ReportType.COVERAGE
    ).exists()
    mocked_call.assert_called_with(repository.repoid, commit.commitid, "code1")


def test_reports_post_no_auth(db, mocker):
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    token = "BAD"
    commit = CommitFactory(repository=repository)
    repository.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + token)
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(url, data={"code": "code1"})

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 401
    assert (
        response.json().get("detail")
        == "Failed token authentication, please double-check that your repository token matches in the Codecov UI, "
        "or review the docs https://docs.codecov.com/docs/adding-the-codecov-token"
    )


def test_reports_post_tokenless(client, db, mocker):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=False,
    )
    commit = CommitFactory(repository=repository)
    repository.save()

    fake_provider_service = MagicMock(
        name="fake_provider_service",
        get_pull_request=AsyncMock(
            return_value={
                "base": {"slug": f"codecov/{repository.name}"},
                "head": {"slug": f"someone/{repository.name}"},
            }
        ),
    )
    mocker.patch.object(
        RepoProviderService, "get_adapter", return_value=fake_provider_service
    )

    client = APIClient()
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(
        url,
        data={"code": "code1"},
        headers={"X-Tokenless": f"someone/{repository.name}", "X-Tokenless-PR": "4"},
    )

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 201
    assert CommitReport.objects.filter(
        commit_id=commit.id, code="code1", report_type=CommitReport.ReportType.COVERAGE
    ).exists()
    mocked_call.assert_called_with(repository.repoid, commit.commitid, "code1")
    fake_provider_service.get_pull_request.assert_called_with("4")


def test_reports_post_tokenless_fail(client, db, mocker):
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=False,
    )
    commit = CommitFactory(repository=repository)
    repository.save()

    fake_provider_service = MagicMock(
        name="fake_provider_service",
        get_pull_request=AsyncMock(
            return_value={
                "base": {"slug": f"codecov/{repository.name}"},
                "head": {"slug": f"someone/{repository.name}"},
            }
        ),
    )
    mocker.patch.object(
        RepoProviderService, "get_adapter", return_value=fake_provider_service
    )

    client = APIClient()
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )
    response = client.post(
        url,
        data={"code": "code1"},
        headers={"X-Tokenless": "someone/bad", "X-Tokenless-PR": "4"},
    )

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    assert response.status_code == 401
    assert response.json().get("detail") == "Not valid tokenless upload"


def test_create_report_already_exists(client, db, mocker):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
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
    assert CommitReport.objects.filter(
        commit_id=commit.id, code="code", report_type=CommitReport.ReportType.COVERAGE
    ).exists()
    mocked_call.assert_called_once()


def test_reports_post_code_as_default(client, db, mocker):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
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
    assert CommitReport.objects.filter(
        commit_id=commit.id, code=None, report_type=CommitReport.ReportType.COVERAGE
    ).exists()
    mocked_call.assert_called_once()


def test_reports_results_post_successful(client, db, mocker):
    mocked_task = mocker.patch("services.task.TaskService.create_report_results")
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
    mocked_task.assert_called_once()


@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_reports_results_post_successful_github_oidc_auth(
    mock_jwks_client, mock_jwt_decode, client, db, mocker
):
    mocked_task = mocker.patch("services.task.TaskService.create_report_results")
    mock_sentry_metrics = mocker.patch("upload.views.reports.sentry_metrics.incr")
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
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    repository.save()
    commit_report.save()

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {token}")
    url = reverse(
        "new_upload.reports_results",
        args=["github", "codecov::::the_repo", commit.commitid, "code"],
    )
    response = client.post(
        url,
        content_type="application/json",
        data={},
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert (
        url
        == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports/code/results"
    )
    assert response.status_code == 201
    assert ReportResults.objects.filter(
        report_id=commit_report.id,
    ).exists()
    mocked_task.assert_called_once()
    mock_sentry_metrics.assert_called_with(
        "upload",
        tags={
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_report_results",
            "repo_visibility": "private",
            "is_using_shelter": "no",
        },
    )


def test_reports_results_already_exists_post_successful(client, db, mocker):
    mocked_task = mocker.patch("services.task.TaskService.create_report_results")
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    report_results = ReportResults.objects.create(
        report=commit_report, state=ReportResults.ReportResultsStates.COMPLETED
    )
    repository.save()
    commit_report.save()
    report_results.save()

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
        report_id=commit_report.id, state=ReportResults.ReportResultsStates.PENDING
    ).exists()
    mocked_task.assert_called_once()


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
