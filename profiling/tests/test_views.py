import re

from django.urls import reverse
from rest_framework.test import APIClient

from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from profiling.models import ProfilingCommit, ProfilingUpload
from services.archive import ArchiveService
from services.task import TaskService


def test_simple_profiling_apicall(db, mocker):
    mocked_call = mocker.patch.object(TaskService, "normalize_profiling_upload")
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="banana.txt",
    )
    repo = RepositoryFactory.create(active=True)
    token = RepositoryTokenFactory.create(repository=repo, token_type="profiling")
    client = APIClient()
    pc = ProfilingCommit.objects.create(
        code="test_simple_profiling_apicall",
        repository=repo,
        version_identifier="newidea",
    )
    url = reverse("create_profiling_upload")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(url, {"profiling": pc.code}, format="json")
    assert response.status_code == 201
    response_json = response.json()
    assert sorted(response_json.keys()) == [
        "created_at",
        "external_id",
        "profiling",
        "raw_upload_location",
    ]
    response_json.pop("external_id")
    response_json.pop("created_at")
    assert response.json() == {
        "profiling": "test_simple_profiling_apicall",
        "raw_upload_location": "banana.txt",
    }
    archive_service = ArchiveService(repo)
    pc = ProfilingCommit.objects.get(repository=repo, version_identifier="newidea")
    pu = ProfilingUpload.objects.get(profiling_commit=pc)
    assert pu.raw_upload_location.startswith(
        f"v4/repos/{archive_service.storage_hash}/profilinguploads/{pc.external_id.hex}"
    )
    assert pu.raw_upload_location.endswith(".txt")
    assert re.match(
        r"v4/repos/[A-F0-9]{32}/profilinguploads/[a-f0-9]{32}/[-a-f0-9]{36}.txt",
        pu.raw_upload_location,
    )
    assert pu.normalized_location is None
    assert pu.normalized_at is None
    mocked_call.assert_called_with(pu.id)


def test_creating_profiling_commit_no_code(db):
    repo = RepositoryFactory.create(active=True)
    token = RepositoryTokenFactory.create(repository=repo, token_type="profiling")
    client = APIClient()
    assert not ProfilingCommit.objects.filter(repository=repo).exists()
    url = reverse("create_profiling_version")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(
        url,
        {"environment": "production", "version_identifier": "v1.0.9",},
        format="json",
    )
    assert response.status_code == 400
    assert response.json() == {"code": ["This field is required."]}
    assert not ProfilingCommit.objects.filter(repository=repo).exists()


def test_creating_profiling_commit_does_not_exist(db, mocker):
    repo = RepositoryFactory.create(active=True)
    token = RepositoryTokenFactory.create(repository=repo, token_type="profiling")
    client = APIClient()
    assert not ProfilingCommit.objects.filter(
        repository=repo, code="productionv1.0.9"
    ).exists()
    url = reverse("create_profiling_version")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(
        url,
        {
            "environment": "production",
            "version_identifier": "v1.0.9",
            "code": "productionv1.0.9",
        },
        format="json",
    )
    assert response.status_code == 201
    response_json = response.json()
    assert sorted(response_json.keys()) == [
        "code",
        "created_at",
        "environment",
        "external_id",
        "version_identifier",
    ]
    response_json.pop("external_id")
    response_json.pop("created_at")
    assert response.json() == {
        "environment": "production",
        "version_identifier": "v1.0.9",
        "code": "productionv1.0.9",
    }
    pc = ProfilingCommit.objects.get(
        repository=repo, environment="production", version_identifier="v1.0.9"
    )
    assert pc.uploads.count() == 0


def test_creating_profiling_commit_already_exist(db, mocker):
    repo = RepositoryFactory.create(active=True)
    token = RepositoryTokenFactory.create(repository=repo, token_type="profiling")
    client = APIClient()
    pc = ProfilingCommit.objects.create(
        repository=repo,
        environment="production",
        version_identifier="v1.0.9",
        code="productionv1.0.9",
    )
    assert ProfilingCommit.objects.filter(
        repository=repo, environment="production", version_identifier="v1.0.9"
    ).exists()
    url = reverse("create_profiling_version")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(
        url,
        {
            "environment": "production",
            "version_identifier": "v1.0.9",
            "code": "productionv1.0.9",
        },
        format="json",
    )
    assert response.status_code == 201
    response_json = response.json()
    assert sorted(response_json.keys()) == [
        "code",
        "created_at",
        "environment",
        "external_id",
        "version_identifier",
    ]
    response_json.pop("external_id")
    response_json.pop("created_at")
    assert response.json() == {
        "environment": "production",
        "version_identifier": "v1.0.9",
        "code": "productionv1.0.9",
    }
    pc = ProfilingCommit.objects.get(
        repository=repo, environment="production", version_identifier="v1.0.9"
    )
    assert pc.uploads.count() == 0
