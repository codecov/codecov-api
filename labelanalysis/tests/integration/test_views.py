from uuid import uuid4

from django.urls import reverse
from rest_framework.test import APIClient
from shared.celery_config import label_analysis_task_name
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)

from labelanalysis.models import (
    LabelAnalysisProcessingError,
    LabelAnalysisRequest,
    LabelAnalysisRequestState,
)
from labelanalysis.tests.factories import LabelAnalysisRequestFactory
from services.task import TaskService
from staticanalysis.tests.factories import StaticAnalysisSuiteFactory


def test_simple_label_analysis_call_flow(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit = CommitFactory.create(repository=commit.repository)
    StaticAnalysisSuiteFactory.create(commit=base_commit)
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
        "errors": [],
    }
    assert response_json == expected_response_json
    mocked_task_service.assert_called_with(
        label_analysis_task_name,
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


def test_simple_label_analysis_call_flow_same_commit_error(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("create_label_analysis")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    payload = {
        "base_commit": commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
    }
    response = client.post(
        url,
        payload,
        format="json",
    )
    assert response.status_code == 400
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 0
    response_json = response.json()
    expected_response_json = {
        "base_commit": ["Base and head must be different commits"]
    }
    assert response_json == expected_response_json
    assert not mocked_task_service.called


def test_simple_label_analysis_call_flow_with_fallback_on_base(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit_parent_parent = CommitFactory.create(repository=commit.repository)
    base_commit_parent = CommitFactory.create(
        parent_commit_id=base_commit_parent_parent.commitid,
        repository=commit.repository,
    )
    base_commit = CommitFactory.create(
        parent_commit_id=base_commit_parent.commitid, repository=commit.repository
    )
    StaticAnalysisSuiteFactory.create(commit=base_commit_parent_parent)
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
    assert produced_object.base_commit == base_commit_parent_parent
    assert produced_object.head_commit == commit
    assert produced_object.requested_labels is None
    assert produced_object.state_id == LabelAnalysisRequestState.CREATED.db_id
    assert produced_object.result is None
    response_json = response.json()
    expected_response_json = {
        "base_commit": base_commit_parent_parent.commitid,
        "head_commit": commit.commitid,
        "requested_labels": None,
        "result": None,
        "state": "created",
        "external_id": str(produced_object.external_id),
        "errors": [],
    }
    assert response_json == expected_response_json
    mocked_task_service.assert_called_with(
        label_analysis_task_name,
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


def test_simple_label_analysis_call_flow_with_fallback_on_base_error_too_long(
    db, mocker
):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    repository = RepositoryFactory.create(active=True)
    commit = CommitFactory.create(repository=repository)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit_root = CommitFactory.create(repository=repository)
    StaticAnalysisSuiteFactory.create(commit=base_commit_root)
    current = base_commit_root
    attempted_commit_list = [base_commit_root.commitid]
    for i in range(12):
        current = CommitFactory.create(
            parent_commit_id=current.commitid, repository=repository
        )
        attempted_commit_list.append(current.commitid)
    base_commit = current
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
    assert response.status_code == 400
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 0
    response_json = response.json()
    # reverse and get 10 first elements, thats how far we look
    attempted_commit_list = ",".join(list(reversed(attempted_commit_list))[:10])
    expected_response_json = {
        "base_commit": [
            f"No possible commits have static analysis sent. Attempted too many commits: {attempted_commit_list}"
        ]
    }
    assert response_json == expected_response_json
    assert not mocked_task_service.called


def test_simple_label_analysis_call_flow_with_fallback_on_base_error(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit_parent_parent = CommitFactory.create(repository=commit.repository)
    base_commit_parent = CommitFactory.create(
        parent_commit_id=base_commit_parent_parent.commitid,
        repository=commit.repository,
    )
    base_commit = CommitFactory.create(
        parent_commit_id=base_commit_parent.commitid, repository=commit.repository
    )
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
    assert response.status_code == 400
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 0
    response_json = response.json()
    attempted_commit_list = ",".join(
        [
            base_commit.commitid,
            base_commit_parent.commitid,
            base_commit_parent_parent.commitid,
        ]
    )
    expected_response_json = {
        "base_commit": [
            f"No possible commits have static analysis sent. Attempted commits: {attempted_commit_list}"
        ]
    }
    assert response_json == expected_response_json
    assert not mocked_task_service.called


def test_simple_label_analysis_call_flow_with_fallback_on_head_error(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    repository = RepositoryFactory.create(active=True)
    head_commit_parent = CommitFactory.create(repository=repository)
    head_commit = CommitFactory.create(
        parent_commit_id=head_commit_parent.commitid, repository=repository
    )
    base_commit = CommitFactory.create(repository=repository)
    StaticAnalysisSuiteFactory.create(commit=base_commit)
    StaticAnalysisSuiteFactory.create(commit=head_commit_parent)
    token = RepositoryTokenFactory.create(
        repository=head_commit.repository, token_type="static_analysis"
    )
    client = APIClient()
    url = reverse("create_label_analysis")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    payload = {
        "base_commit": base_commit.commitid,
        "head_commit": head_commit.commitid,
        "requested_labels": None,
    }
    response = client.post(
        url,
        payload,
        format="json",
    )
    assert response.status_code == 400
    assert LabelAnalysisRequest.objects.filter(head_commit=head_commit).count() == 0
    assert (
        LabelAnalysisRequest.objects.filter(head_commit=head_commit_parent).count() == 0
    )
    response_json = response.json()
    expected_response_json = {"head_commit": ["No static analysis found"]}
    assert response_json == expected_response_json
    assert not mocked_task_service.called


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
    larq_processing_error = LabelAnalysisProcessingError(
        label_analysis_request=label_analysis,
        error_code="Missing FileSnapshot",
        error_params={"message": "Something is wrong"},
    )
    label_analysis.save()
    larq_processing_error.save()
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
        "errors": [
            {
                "error_code": "Missing FileSnapshot",
                "error_params": {"message": "Something is wrong"},
            }
        ],
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


def test_simple_label_analysis_get_does_not_exist(db, mocker):
    token = RepositoryTokenFactory.create(
        repository__active=True, token_type="static_analysis"
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    get_url = reverse("view_label_analysis", kwargs=dict(external_id=uuid4()))
    response = client.get(
        get_url,
        format="json",
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "No such Label Analysis exists"}


def test_simple_label_analysis_put_labels(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit = CommitFactory.create(repository=commit.repository)
    StaticAnalysisSuiteFactory.create(commit=base_commit)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    label_analysis = LabelAnalysisRequestFactory.create(
        head_commit=commit,
        base_commit=base_commit,
        state_id=LabelAnalysisRequestState.CREATED.db_id,
        result=None,
    )
    label_analysis.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 1
    produced_object = LabelAnalysisRequest.objects.get(head_commit=commit)
    assert produced_object == label_analysis
    assert produced_object.requested_labels is None
    expected_response_json = {
        "base_commit": base_commit.commitid,
        "head_commit": commit.commitid,
        "requested_labels": ["label_1", "label_2", "label_3"],
        "result": None,
        "state": "created",
        "external_id": str(produced_object.external_id),
        "errors": [],
    }
    patch_url = reverse(
        "view_label_analysis", kwargs=dict(external_id=produced_object.external_id)
    )
    response = client.patch(
        patch_url,
        format="json",
        data={
            "requested_labels": ["label_1", "label_2", "label_3"],
            "base_commit": base_commit.commitid,
            "head_commit": commit.commitid,
        },
    )
    assert response.status_code == 200
    assert response.json() == expected_response_json
    mocked_task_service.assert_called_with(
        label_analysis_task_name,
        kwargs=dict(request_id=label_analysis.id),
        apply_async_kwargs=dict(),
    )


def test_simple_label_analysis_put_labels_wrong_base_return_404(db, mocker):
    mocked_task_service = mocker.patch.object(TaskService, "schedule_task")
    commit = CommitFactory.create(repository__active=True)
    StaticAnalysisSuiteFactory.create(commit=commit)
    base_commit = CommitFactory.create(repository=commit.repository)
    StaticAnalysisSuiteFactory.create(commit=base_commit)
    token = RepositoryTokenFactory.create(
        repository=commit.repository, token_type="static_analysis"
    )
    label_analysis = LabelAnalysisRequestFactory.create(
        head_commit=commit,
        base_commit=base_commit,
        state_id=LabelAnalysisRequestState.CREATED.db_id,
        result=None,
    )
    label_analysis.save()
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    assert LabelAnalysisRequest.objects.filter(head_commit=commit).count() == 1
    produced_object = LabelAnalysisRequest.objects.get(head_commit=commit)
    assert produced_object == label_analysis
    assert produced_object.requested_labels is None
    patch_url = reverse(
        "view_label_analysis", kwargs=dict(external_id=produced_object.external_id)
    )
    response = client.patch(
        patch_url,
        format="json",
        data={
            "requested_labels": ["label_1", "label_2", "label_3"],
            "base_commit": "not_base_commit",
            "head_commit": commit.commitid,
        },
    )
    assert response.status_code == 404
    mocked_task_service.assert_not_called()
