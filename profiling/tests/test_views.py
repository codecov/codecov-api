import re

from rest_framework.test import APIClient
from django.urls import reverse

from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from profiling.models import ProfilingUpload, ProfilingCommit
from services.task import TaskService
from services.archive import ArchiveService


def test_simple_profiling_apicall(db, mocker):
    mocked_call = mocker.patch.object(TaskService, "normalize_profiling_upload")
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="banana.txt",
    )
    repo = RepositoryFactory.create(active=True)
    token = RepositoryTokenFactory.create(repository=repo, token_type="profiling")
    client = APIClient()
    url = reverse("create_profiling_upload")
    client.credentials(HTTP_AUTHORIZATION="repotoken " + token.key)
    response = client.post(url, {"profiling": "newidea"}, format="json")
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
        "profiling": "newidea",
        "raw_upload_location": "banana.txt",
    }
    archive_service = ArchiveService(repo)
    pc = ProfilingCommit.objects.get(repository=repo, version_identifier="newidea")
    pu = ProfilingUpload.objects.get(profiling_commit=pc)
    assert pu.raw_upload_location.startswith(
        f"v4/repos/{archive_service.storage_hash}/profilinguploads/newidea"
    )
    assert pu.raw_upload_location.endswith(".txt")
    assert re.match(
        r"v4/repos/[A-F0-9]{32}/profilinguploads/newidea/[-a-f0-9]{36}.txt",
        pu.raw_upload_location,
    )
    assert pu.normalized_location is None
    assert pu.normalized_at is None
    mocked_call.assert_called_with(pu.id)
