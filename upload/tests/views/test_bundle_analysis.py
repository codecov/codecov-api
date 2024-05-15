import json
import re
from unittest.mock import ANY, patch

from django.urls import reverse
from rest_framework.test import APIClient

from codecov_auth.tests.factories import OrganizationLevelTokenFactory
from core.models import Commit
from core.tests.factories import CommitFactory, RepositoryFactory
from services.redis_configuration import get_redis_connection
from services.task import TaskService


def test_upload_bundle_analysis(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mock_sentry_metrics = mocker.patch(
        "upload.views.bundle_analysis.sentry_metrics.incr"
    )
    create_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create()
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {repository.upload_token}")

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit_sha,
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )
    assert res.status_code == 201

    # returns presigned storage URL
    assert res.json() == {"url": "test-presigned-put"}

    create_presigned_put.assert_called_once_with("bundle-analysis", ANY, 30)
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
    args = redis.rpop(f"uploads/{repository.repoid}/{commit_sha}/bundle_analysis")
    assert json.loads(args) == {
        "reportid": reportid,
        "build": "test-build",
        "build_url": "test-build-url",
        "job": "test-job",
        "service": "test-service",
        "url": f"v1/uploads/{reportid}.json",
        "commit": commit_sha,
        "report_code": None,
    }

    # sets latest upload timestamp
    ts = redis.get(f"latest_upload/{repository.repoid}/{commit_sha}/bundle_analysis")
    assert ts

    # triggers upload task
    upload.assert_called_with(
        commitid=commit_sha,
        repoid=repository.repoid,
        countdown=4,
        report_code=None,
        report_type="bundle_analysis",
    )
    mock_sentry_metrics.assert_called_with(
        "upload",
        tags={
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "repo_visibility": "private",
            "is_using_shelter": "no",
        },
    )


def test_upload_bundle_analysis_org_token(db, client, mocker, mock_redis):
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
        reverse("upload-bundle-analysis"),
        {
            "commit": "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef",
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 201


def test_upload_bundle_analysis_existing_commit(db, client, mocker, mock_redis):
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
        reverse("upload-bundle-analysis"),
        {
            "commit": commit.commitid,
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 201

    upload.assert_called_with(
        commitid=commit.commitid,
        repoid=repository.repoid,
        countdown=4,
        report_code=None,
        report_type="bundle_analysis",
    )


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
        reverse("upload-bundle-analysis"),
        {
            "commit": commit.commitid,
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json() == {"slug": ["This field is required."]}
    assert not upload.called

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 400
    assert res.json() == {"commit": ["This field is required."]}
    assert not upload.called


def test_upload_bundle_analysis_invalid_token(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    create_presigned_put = mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create()
    commit = CommitFactory.create(repository=repository)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="token 2a869881-9c0f-4754-b790-3f5920be3605")

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit.commitid,
        },
        format="json",
    )
    assert res.status_code == 401
    assert res.json() == {
        "detail": "Failed token authentication, please double-check that your repository token matches in the Codecov UI, "
        "or review the docs https://docs.codecov.com/docs/adding-the-codecov-token"
    }
    assert not upload.called


@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_upload_bundle_analysis_github_oidc_auth(
    mock_jwks_client, mock_jwt_decode, db, mocker
):
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    repository = RepositoryFactory()
    mock_jwt_decode.return_value = {
        "repository": f"url/{repository.name}",
        "repository_owner": repository.author.username,
        "iss": "https://token.actions.githubusercontent.com",
    }
    token = "ThisValueDoesNotMatterBecauseOf_mock_jwt_decode"

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {token}")

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef",
            "slug": f"{repository.author.username}::::{repository.name}",
        },
        format="json",
    )
    assert res.status_code == 201
