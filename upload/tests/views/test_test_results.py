import json
import re
from unittest.mock import ANY

from django.urls import reverse
from rest_framework.test import APIClient

from codecov_auth.tests.factories import OrganizationLevelTokenFactory
from core.models import Commit
from core.tests.factories import CommitFactory, RepositoryFactory
from services.redis_configuration import get_redis_connection
from services.task import TaskService


def test_upload_test_results(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    create_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create()
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {repository.upload_token}")

    res = client.post(
        reverse("upload-test-results"),
        {
            "commit": commit_sha,
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
        },
        format="json",
    )
    assert res.status_code == 201

    # returns presigned storage URL
    assert res.json() == {"raw_upload_location": "test-presigned-put"}

    create_presigned_put.assert_called_once_with("test_results", ANY, 10)
    call = create_presigned_put.mock_calls[0]
    _, storage_path, _ = call.args
    match = re.match(r"v1/uploads/([\d\w\-]+)\.json", storage_path)
    assert match
    (reportid,) = match.groups()

    # creates commit
    commit = Commit.objects.get(commitid=commit_sha)
    assert commit

    # saves args in Redis
    redis = get_redis_connection()
    args = redis.rpop(f"uploads/{repository.repoid}/{commit_sha}/test_results")
    assert json.loads(args) == {
        "reportid": reportid,
        "build": "test-build",
        "build_url": "test-build-url",
        "job": "test-job",
        "service": "test-service",
        "url": f"v1/uploads/{reportid}.json",
        "commit": commit_sha,
        "report_code": None,
        "flags": None,
    }

    # sets latest upload timestamp
    ts = redis.get(f"latest_upload/{repository.repoid}/{commit_sha}/test_results")
    assert ts

    # triggers upload task
    upload.assert_called_with(
        commitid=commit_sha,
        repoid=repository.repoid,
        countdown=0,
        report_code=None,
        report_type="test_results",
    )


def test_test_results_org_token(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    create_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create()
    org_token = OrganizationLevelTokenFactory.create(owner=repository.author)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {org_token.token}")

    res = client.post(
        reverse("upload-test-results"),
        {
            "commit": "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef",
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 201


def test_upload_bundle_analysis_missing_args(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    create_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create()
    commit = CommitFactory.create(repository=repository)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {repository.upload_token}")

    res = client.post(
        reverse("upload-test-results"),
        {
            "commit": commit.commitid,
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json() == {"slug": ["This field is required."]}
    assert not upload.called

    res = client.post(
        reverse("upload-test-results"),
        {
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json() == {"commit": ["This field is required."]}
    assert not upload.called
