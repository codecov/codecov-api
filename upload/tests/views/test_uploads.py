from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport, ReportSession
from upload.views.uploads import CanDoCoverageUploadsPermission

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory


def test_uploads_get_not_allowed(client, db):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "report-id"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/report-id/uploads"
    client.force_login(OwnerFactory(plan=BASIC_PLAN_NAME))
    res = client.get(url)
    assert res.status_code == 405


def test_uploads_post_empty(db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit)
    report = ReportSession.objects.create(report=commit_report, name="some_name")
    repository.save()
    commit_report.save()
    report.save()

    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)
    url = reverse(
        "new_upload.uploads",
        args=[repository.name, commit.commitid, report.report_id],
    )
    response = client.post(
        url,
        {"state": "uploaded"},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == 201
    assert all(
        map(
            lambda x: x in response_json.keys(),
            ["external_id", "created_at", "report", "raw_upload_location"],
        )
    )
