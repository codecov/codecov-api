import json
import re
from unittest.mock import ANY, patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
)
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from core.models import Commit
from services.redis_configuration import get_redis_connection
from services.task import TaskService
from timeseries.models import Dataset, MeasurementName


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_success(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
    )
    create_presigned_put = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
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
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
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
        "bundle_analysis_compare_sha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
    }

    # sets latest upload timestamp
    ts = redis.get(f"latest_upload/{repository.repoid}/{commit_sha}/bundle_analysis")
    assert ts

    # triggers upload task
    upload.assert_called_with(
        commitid=commit_sha,
        repoid=repository.repoid,
        report_code=None,
        report_type="bundle_analysis",
        arguments=ANY,
        countdown=4,
    )
    mock_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
@override_settings(SHELTER_SHARED_SECRET="shelter-shared-secret")
def test_upload_bundle_analysis_success_shelter(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
    )
    create_presigned_put = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
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
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "storage_path": "shelter/test/path.txt",
            "upload_external_id": "test-47078f85-2cee-4511-b38d-183c334ef43b",
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
        "bundle_analysis_compare_sha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
    }

    # sets latest upload timestamp
    ts = redis.get(f"latest_upload/{repository.repoid}/{commit_sha}/bundle_analysis")
    assert ts

    # triggers upload task
    upload.assert_called_with(
        commitid=commit_sha,
        repoid=repository.repoid,
        report_code=None,
        report_type="bundle_analysis",
        arguments=ANY,
        countdown=4,
    )
    mock_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_org_token(db, client, mocker, mock_redis):
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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
    mock_metrics.assert_called_with(
        **{
            "agent": "unknown-user-agent",
            "version": "unknown-user-agent",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_existing_commit(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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
        report_code=None,
        report_type="bundle_analysis",
        arguments=ANY,
        countdown=4,
    )
    mock_metrics.assert_called_with(
        **{
            "agent": "unknown-user-agent",
            "version": "unknown-user-agent",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


def test_upload_bundle_analysis_missing_args(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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
    mock_metrics.assert_called_with(
        **{
            "agent": "unknown-user-agent",
            "version": "unknown-user-agent",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "start",
        },
    )


def test_upload_bundle_analysis_invalid_token(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
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
    assert res.json() == {"detail": "Not valid tokenless upload"}
    assert not upload.called


@pytest.mark.django_db(databases={"default", "timeseries"})
@patch("upload.helpers.jwt.decode")
@patch("upload.helpers.PyJWKClient")
def test_upload_bundle_analysis_github_oidc_auth(
    mock_jwks_client, mock_jwt_decode, db, mocker
):
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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
    mock_metrics.assert_called_with(
        **{
            "agent": "unknown-user-agent",
            "version": "unknown-user-agent",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_measurement_datasets_created(
    db, client, mocker, mock_redis
):
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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

    supported_bundle_analysis_measurement_types = [
        MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_FONT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_IMAGE_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_JAVASCRIPT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_REPORT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_STYLESHEET_SIZE,
    ]
    for measurement_type in supported_bundle_analysis_measurement_types:
        assert Dataset.objects.filter(
            name=measurement_type.value,
            repository_id=repository.pk,
        ).exists()

    mock_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@override_settings(TIMESERIES_ENABLED=False)
@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_measurement_timeseries_disabled(
    db, client, mocker, mock_redis
):
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
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

    supported_bundle_analysis_measurement_types = [
        MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_FONT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_IMAGE_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_JAVASCRIPT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_REPORT_SIZE,
        MeasurementName.BUNDLE_ANALYSIS_STYLESHEET_SIZE,
    ]
    for measurement_type in supported_bundle_analysis_measurement_types:
        assert not Dataset.objects.filter(
            name=measurement_type.value,
            repository_id=repository.pk,
        ).exists()

    mock_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_no_repo(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mocker.patch.object(TaskService, "upload")
    mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
    )

    repository = RepositoryFactory.create()
    org_token = OrganizationLevelTokenFactory.create(owner=repository.author)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"token {org_token.token}")

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef",
            "slug": "FakeUser::::NonExistentName",
        },
        format="json",
    )
    assert res.status_code == 404
    assert res.json() == {"detail": "Repository not found."}
    assert not upload.called

    mock_metrics.assert_called_with(
        **{
            "agent": "unknown-user-agent",
            "version": "unknown-user-agent",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "start",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_tokenless_success(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")
    mock_metrics = mocker.patch(
        "upload.views.bundle_analysis.BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER.labels"
    )

    create_presigned_put = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create(private=False)
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    client = APIClient()

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit_sha,
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "branch": "f1:main",
            "git_service": "github",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert res.status_code == 201

    # returns presigned storage URL
    assert res.json() == {"url": "test-presigned-put"}

    assert upload.called
    create_presigned_put.assert_called_once_with("bundle-analysis", ANY, 30)

    mock_metrics.assert_called_with(
        **{
            "agent": "cli",
            "version": "0.4.7",
            "action": "bundle_analysis",
            "endpoint": "bundle_analysis",
            "is_using_shelter": "no",
            "position": "end",
        },
    )


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_true_tokenless_success(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")

    create_presigned_put = mocker.patch(
        "shared.api_archive.archive.StorageService.create_presigned_put",
        return_value="test-presigned-put",
    )

    repository = RepositoryFactory.create(
        private=False,
        author__upload_token_required_for_public_repos=False,
        author__service="github",
    )
    client = APIClient()

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": "any",
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "branch": "f1:main",
            "git_service": "github",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert res.status_code == 201

    # returns presigned storage URL
    assert res.json() == {"url": "test-presigned-put"}

    assert upload.called
    create_presigned_put.assert_called_once_with("bundle-analysis", ANY, 30)


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_tokenless_no_repo(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")

    repository = RepositoryFactory.create(private=False)
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    client = APIClient()

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit_sha,
            "slug": f"fakerepo::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "branch": "f1:main",
            "git_service": "github",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert res.status_code == 401
    assert res.json() == {"detail": "Not valid tokenless upload"}
    assert not upload.called


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_tokenless_no_git_service(
    db, client, mocker, mock_redis
):
    upload = mocker.patch.object(TaskService, "upload")

    repository = RepositoryFactory.create(private=False)
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    client = APIClient()

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit_sha,
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "branch": "f1:main",
            "git_service": "fakegitservice",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert res.status_code == 401
    assert res.json() == {"detail": "Not valid tokenless upload"}
    assert not upload.called


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_tokenless_bad_json(db, client, mocker, mock_redis):
    upload = mocker.patch.object(TaskService, "upload")

    repository = RepositoryFactory.create(private=False)
    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"

    from json import JSONDecodeError

    with patch(
        "codecov_auth.authentication.repo_auth.json.loads",
        side_effect=JSONDecodeError("mocked error", doc="doc", pos=0),
    ):
        client = APIClient()

        res = client.post(
            reverse("upload-bundle-analysis"),
            {
                "commit": commit_sha,
                "slug": f"{repository.author.username}::::{repository.name}",
                "build": "test-build",
                "buildURL": "test-build-url",
                "job": "test-job",
                "service": "test-service",
                "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
                "branch": "f1:main",
                "git_service": "github",
            },
            format="json",
            headers={"User-Agent": "codecov-cli/0.4.7"},
        )

        assert res.status_code == 401
        assert not upload.called


@pytest.mark.django_db(databases={"default", "timeseries"})
def test_upload_bundle_analysis_tokenless_mismatched_branch(
    db, client, mocker, mock_redis
):
    upload = mocker.patch.object(TaskService, "upload")

    commit_sha = "6fd5b89357fc8cdf34d6197549ac7c6d7e5977ef"
    repository = RepositoryFactory.create(
        private=False,
        author__upload_token_required_for_public_repos=True,
    )
    CommitFactory.create(repository=repository, commitid=commit_sha, branch="main")

    client = APIClient()

    res = client.post(
        reverse("upload-bundle-analysis"),
        {
            "commit": commit_sha,
            "slug": f"{repository.author.username}::::{repository.name}",
            "build": "test-build",
            "buildURL": "test-build-url",
            "job": "test-job",
            "service": "test-service",
            "compareSha": "6fd5b89357fc8cdf34d6197549ac7c6d7e5aaaaa",
            "branch": "f1:main",
            "git_service": "github",
        },
        format="json",
        headers={"User-Agent": "codecov-cli/0.4.7"},
    )

    assert res.status_code == 401
    assert res.json() == {"detail": "Not valid tokenless upload"}
    assert not upload.called
