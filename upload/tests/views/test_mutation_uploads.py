from django.urls import reverse
from rest_framework.test import APIClient

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.models import CommitReport, ReportSession
from services.task import TaskService


def test_mutation_upload(db, mocker):
    mocked_call = mocker.patch.object(TaskService, "mutation_test_upload")
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )

    repository = RepositoryFactory(name="the_repo", author__username="codecov")
    commit = CommitFactory(repository=repository)
    commit_report = CommitReport.objects.create(commit=commit)
    # REVIEW - this seems not right. Shouldn't the endpoint post create exactly this object?
    # But I can't find a way for it to work withou passing the reportid
    report = ReportSession.objects.create(report=commit_report, name="some_name")
    commit_report.save()
    report.save()
    owner = OwnerFactory(plan=BASIC_PLAN_NAME)
    client = APIClient()
    client.force_authenticate(user=owner)

    url = reverse(
        "new_upload.mutation_uploads",
        args=[repository.name, commit.commitid, report.report_id],
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
                "report",
                "raw_upload_location",
            ],
        )
    )
    assert response_json["raw_upload_location"] == "presigned put"
    mocked_call.assert_called()
