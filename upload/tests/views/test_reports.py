from unittest.mock import patch

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from reports.models import CommitReport, ReportResults
from reports.tests.factories import ReportResultsFactory
from services.task.task import TaskService
from upload.views.uploads import CanDoCoverageUploadsPermission


def test_reports_get_not_allowed(client, mocker, db):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    owner = OwnerFactory(service="github")
    repo = RepositoryFactory(name="the_repo", private=False, author=owner)
    commit = CommitFactory(repository=repo)
    commit.branch = "someone:branch"
    owner.save()
    repo.save()
    commit.save()
    headers = {}
    url = reverse(
        "new_upload.reports",
        args=["github", f"{owner.username}::::the_repo", commit.commitid],
    )
    assert (
        url
        == f"/upload/github/{owner.username}::::the_repo/commits/{commit.commitid}/reports"
    )
    res = client.get(url, **headers)
    assert res.status_code == 405


def test_deactivated_repo(db):
    repo = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        active=True,
        activated=False,
    )
    commit = CommitFactory(repository=repo)
    repo.save()
    commit.save()
    repo_slug = f"{repo.author.username}::::{repo.name}"

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token " + repo.upload_token)
    url = reverse(
        "new_upload.reports",
        args=["github", repo_slug, commit.commitid],
    )
    response = client.post(
        url, data={"code": "code1"}, headers={"User-Agent": "codecov-cli/0.4.7"}
    )
    response_json = response.json()
    assert response.status_code == 400
    assert response_json == [
        f"This repository is deactivated. To resume uploading to it, please activate the repository in the codecov UI: {settings.CODECOV_DASHBOARD_URL}/github/codecov/the_repo/config/general"
    ]


def test_reports_post(client, db, mocker):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    mock_prometheus_metrics = mocker.patch("upload.metrics.API_UPLOAD_COUNTER.labels")
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
    mock_prometheus_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_report",
            "repo_visibility": "private",
            "is_using_shelter": "no",
            "position": "end",
            "upload_version": None,
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


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("branch", ["main", "fork:branch", "someone/fork:branch"])
@pytest.mark.parametrize(
    "branch_sent",
    [
        None,
        "branch",
        "fork:branch",
        "someone/fork:branch",
    ],
)
def test_reports_post_tokenless(client, db, mocker, private, branch, branch_sent):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        author__upload_token_required_for_public_repos=True,
        private=private,
    )
    commit = CommitFactory(repository=repository)
    commit.branch = branch
    repository.save()
    commit.save()

    client = APIClient()
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )

    data = {"code": "code1"}
    if branch_sent:
        data["branch"] = branch_sent
    response = client.post(
        url,
        data=data,
        headers={},
    )

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )
    if private is False and ":" in branch:
        assert response.status_code == 201
        assert CommitReport.objects.filter(
            commit_id=commit.id,
            code="code1",
            report_type=CommitReport.ReportType.COVERAGE,
        ).exists()
        mocked_call.assert_called_with(repository.repoid, commit.commitid, "code1")
    else:
        assert response.status_code == 401
        assert not CommitReport.objects.filter(
            commit_id=commit.id,
            code="code1",
            report_type=CommitReport.ReportType.COVERAGE,
        ).exists()
        assert response.json().get("detail") == "Not valid tokenless upload"


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("branch", ["main", "fork:branch", "someone/fork:branch"])
@pytest.mark.parametrize(
    "branch_sent",
    [
        None,
        "branch",
        "fork:branch",
        "someone/fork:branch",
    ],
)
@pytest.mark.parametrize("upload_token_required_for_public_repos", [True, False])
def test_reports_post_upload_token_required_auth_check(
    client,
    db,
    mocker,
    private,
    branch,
    branch_sent,
    upload_token_required_for_public_repos,
):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=private,
        author__upload_token_required_for_public_repos=upload_token_required_for_public_repos,
    )
    commit = CommitFactory(repository=repository)
    commit.branch = branch
    repository.save()
    commit.save()

    client = APIClient()
    url = reverse(
        "new_upload.reports",
        args=["github", "codecov::::the_repo", commit.commitid],
    )

    data = {"code": "code1"}
    if branch_sent:
        data["branch"] = branch_sent
    response = client.post(
        url,
        data=data,
        headers={},
    )

    assert (
        url == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports"
    )

    # when TokenlessAuthentication is removed, this test should use `if private == False and upload_token_required_for_public_repos == False:`
    # but TokenlessAuthentication lets some additional uploads through.
    authorized_by_tokenless_auth_class = ":" in branch

    if private == False and (
        upload_token_required_for_public_repos == False
        or authorized_by_tokenless_auth_class
    ):
        assert response.status_code == 201
        assert CommitReport.objects.filter(
            commit_id=commit.id,
            code="code1",
            report_type=CommitReport.ReportType.COVERAGE,
        ).exists()
        mocked_call.assert_called_with(repository.repoid, commit.commitid, "code1")
    else:
        assert response.status_code == 401
        assert not CommitReport.objects.filter(
            commit_id=commit.id,
            code="code1",
            report_type=CommitReport.ReportType.COVERAGE,
        ).exists()
        assert response.json().get("detail") == "Not valid tokenless upload"


def test_create_report_already_exists(client, db, mocker):
    mocked_call = mocker.patch.object(TaskService, "preprocess_upload")
    repository = RepositoryFactory(
        name="the_repo", author__username="codecov", author__service="github"
    )
    commit = CommitFactory(repository=repository)
    CommitReport.objects.create(commit=commit, code="code")

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
    mocked_call.assert_not_called()


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
    mock_prometheus_metrics = mocker.patch("upload.metrics.API_UPLOAD_COUNTER.labels")
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
    mock_prometheus_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "coverage",
            "endpoint": "create_report_results",
            "repo_visibility": "private",
            "is_using_shelter": "no",
            "position": "end",
            "upload_version": None,
        },
    )


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("branch", ["main", "fork:branch", "someone/fork:branch"])
@pytest.mark.parametrize(
    "branch_sent",
    [
        None,
        "branch",
        "fork:branch",
        "someone/fork:branch",
    ],
)
@pytest.mark.parametrize("upload_token_required_for_public_repos", [True, False])
def test_reports_results_post_upload_token_required_auth_check(
    client,
    db,
    mocker,
    private,
    branch,
    branch_sent,
    upload_token_required_for_public_repos,
):
    mocked_task = mocker.patch("services.task.TaskService.create_report_results")
    repository = RepositoryFactory(
        name="the_repo",
        author__username="codecov",
        author__service="github",
        private=private,
        author__upload_token_required_for_public_repos=upload_token_required_for_public_repos,
    )
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit, code="code")
    commit.branch = branch
    repository.save()
    commit.save()

    client = APIClient()
    url = reverse(
        "new_upload.reports_results",
        args=["github", "codecov::::the_repo", commit.commitid, "code"],
    )

    data = {"code": "code1"}
    if branch_sent:
        data["branch"] = branch_sent
    response = client.post(
        url,
        data=data,
        headers={},
    )

    assert (
        url
        == f"/upload/github/codecov::::the_repo/commits/{commit.commitid}/reports/code/results"
    )

    # when TokenlessAuthentication is removed, this test should use `if private == False and upload_token_required_for_public_repos == False:`
    # but TokenlessAuthentication lets some additional uploads through.
    authorized_by_tokenless_auth_class = ":" in branch

    if private == False and (
        upload_token_required_for_public_repos == False
        or authorized_by_tokenless_auth_class
    ):
        assert response.status_code == 201
        assert ReportResults.objects.filter(
            report_id=commit_report.id,
        ).exists()
        mocked_task.assert_called_once()
    else:
        assert response.status_code == 401
        assert not ReportResults.objects.filter(
            report_id=commit_report.id,
        ).exists()
        assert response.json().get("detail") == "Not valid tokenless upload"


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
    CommitReport.objects.create(commit=commit, code="code")
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
