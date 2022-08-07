from django.urls import reverse
from rest_framework.test import APIClient

from core.tests.factories import CommitFactory, RepositoryTokenFactory
from labelanalysis.models import LabelAnalysisRequest, LabelAnalysisRequestState
from labelanalysis.tests.factories import LabelAnalysisRequestFactory
from services.task import TaskService


def test_simple_label_analysis_call_flow(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    base_commit = CommitFactory.create(repository=commit.repository)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("create_label_analysis")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    payload = {
        "base_commit": base_commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
    }
    response = client.post(
        url,
        payload,
        format="json",
    )
    assert response.status_code == 201
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 1
    produced_object = LabelAnalysisRequest.objects.get(head_commit=commit)
    assert produced_object
    assert produced_object.base_commit == base_commit
    assert produced_object.head_commit == commit
    assert produced_object.requested_labels is None
    assert produced_object.state_id == LabelAnalysisRequestState.CREATED.db_id
    assert produced_object.result is None
    response_json = response.json()
    expected_response_json = {
        "base_commit": base_commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
        "result": None,
        "state": "created",
        "external_id": str(produced_object.external_id),
    }
    assert response_json == expected_response_json
    mocked_task_service.assert_called_with(
        "app.tasks.label_analysis.process",
        kwargs={"request_id": produced_object.id},
        apply_async_kwargs={},
    )
    get_url = reverse(
        "view_label_analysis", kwargs=dict(external_id=produced_object.external_id)
    )
    response = client.get(
        get_url,
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == expected_response_json


def test_simple_label_analysis_only_get(db, mocker):
    commit = CommitFactory.create(repository__active=True)
    base_commit = CommitFactory.create(repository=commit.repository)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    label_analysis = LabelAnalysisRequestFactory.create(
        head_commit=commit,
        base_commit=base_commit,
        state_id=LabelAnalysisRequestState.FINISHED.db_id,
        result={"some": ["result"]},
    )
    label_analysis.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 1
    produced_object = LabelAnalysisRequest.objects.get(head_commit=commit)
    assert produced_object == label_analysis
    expected_response_json = {
        "base_commit": base_commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
        "result": {"some": ["result"]},
        "state": "finished",
        "external_id": str(produced_object.external_id),
    }
    get_url = reverse(
        "view_label_analysis", kwargs=dict(external_id=produced_object.external_id)
    )
    response = client.get(
        get_url,
        format="json",
    )
    assert response.status_code == 200
    assert response.json() == expected_response_json
