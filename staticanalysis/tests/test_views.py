from uuid import uuid4

from django.urls import reverse
from rest_framework.test import APIClient

from core.tests.factories import CommitFactory, RepositoryTokenFactory
from services.task import TaskService
from staticanalysis.models import StaticAnalysisSuite


def test_simple_static_analysis_call_no_uploads_yet(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    mocked_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="banana.txt",
    )
    commit = CommitFactory.create(repository__active=True)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("static_analysis_upload")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    some_uuid, second_uuid = uuid4(), uuid4()
    response = client.post(
        url,
        {
            "commit": commit.commitid,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": some_uuid,
                },
                {
                    "filepath": "banana.cpp",
                    "file_hash": second_uuid,
                },
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert StaticAnalysisSuite.objects.filter(commit=commit).count() == 1
    produced_object = StaticAnalysisSuite.objects.filter(commit=commit).get()
    response_json = response.json()
    assert "filepaths" in response_json
    # Popping and sorting because the order doesn't matter, as long as all are there
    assert sorted(response_json.pop("filepaths"), key=lambda x: x["filepath"]) == [
        {
            "filepath": "banana.cpp",
            "file_hash": str(second_uuid),
            "raw_upload_location": "banana.txt",
            "state": "CREATED",
        },
        {
            "filepath": "path/to/a.py",
            "file_hash": str(some_uuid),
            "raw_upload_location": "banana.txt",
            "state": "CREATED",
        },
    ]
    # Now asserting the remaining of the response
    assert response_json == {
        "external_id": str(produced_object.external_id),
        "commit": commit.commitid,
    }
    mocked_task_service.assert_called_with(
        "app.tasks.staticanalysis.check_suite",
        kwargs={"suite_id": produced_object.id},
        apply_async_kwargs={"countdown": 10},
    )
    mocked_presigned_put.assert_called_with(
        "archive",
        mocker.ANY,
        10,
    )
