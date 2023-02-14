from rest_framework.exceptions import ErrorDetail

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import (
    CommitReportFactory,
    ReportResultsFactory,
    RepositoryFlagFactory,
    UploadFactory,
)
from upload.serializers import (
    CommitReportSerializer,
    CommitSerializer,
    ReportResultsSerializer,
    UploadSerializer,
)


def get_fake_upload():
    user_with_no_uplaods = OwnerFactory()
    user_with_uplaods = OwnerFactory()
    repo = RepositoryFactory.create(author=user_with_uplaods, private=True)
    public_repo = RepositoryFactory.create(author=user_with_uplaods, private=False)
    commit = CommitFactory.create(repository=repo)
    report = CommitReportFactory.create(commit=commit)

    return UploadFactory.create(report=report)


def get_fake_upload_with_flags():
    upload = get_fake_upload()
    flag1 = RepositoryFlagFactory(
        repository=upload.report.commit.repository, flag_name="flag1"
    )
    flag2 = RepositoryFlagFactory(
        repository=upload.report.commit.repository, flag_name="flag2"
    )
    upload.flags.set([flag1, flag2])
    return upload


def test_serialize_upload(transactional_db, mocker):
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    fake_upload = get_fake_upload()
    serializer = UploadSerializer(instance=fake_upload)
    assert (
        "upload_type" in serializer.data
        and serializer.data["upload_type"] == "uploaded"
    )
    new_data = {"env": {"some_var": "some_value"}, "name": "upload name...?"}
    res = serializer.update(fake_upload, new_data)
    assert res == fake_upload
    assert fake_upload.name == "upload name...?"


def test_upload_serializer_contains_expected_fields_no_flags(transactional_db, mocker):
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload = get_fake_upload()
    serializer = UploadSerializer(instance=upload)
    expected_data = {
        "external_id": str(upload.external_id),
        "created_at": upload.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "raw_upload_location": "presigned put",
        "state": upload.state,
        "provider": upload.provider,
        "upload_type": upload.upload_type,
        "ci_url": upload.ci_url,
        "flags": [],
        "env": upload.env,
        "name": upload.name,
    }
    assert serializer.data == expected_data


def test_upload_serializer_contains_expected_fields_with_flags(
    transactional_db, mocker
):
    mocker.patch(
        "services.archive.StorageService.create_presigned_put",
        return_value="presigned put",
    )
    upload = get_fake_upload_with_flags()
    serializer = UploadSerializer(instance=upload)
    expected_data = {
        "external_id": str(upload.external_id),
        "created_at": upload.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "raw_upload_location": "presigned put",
        "state": upload.state,
        "provider": upload.provider,
        "upload_type": upload.upload_type,
        "ci_url": upload.ci_url,
        "flags": ["flag1", "flag2"],
        "env": upload.env,
        "name": upload.name,
    }
    assert serializer.data == expected_data


def test_commit_serializer_contains_expected_fields(transactional_db, mocker):
    commit = CommitFactory.create()
    serializer = CommitSerializer(commit)
    expected_data = {
        "message": commit.message,
        "ci_passed": commit.ci_passed,
        "state": commit.state,
        "repository": {
            "name": commit.repository.name,
            "is_private": commit.repository.private,
            "active": commit.repository.active,
            "language": commit.repository.language,
            "yaml": commit.repository.yaml,
        },
        "author": {
            "avatar_url": commit.author.avatar_url,
            "service": commit.author.service,
            "username": commit.author.username,
            "name": commit.author.name,
            "ownerid": commit.author.ownerid,
        },
        "commitid": commit.commitid,
        "parent_commit_id": commit.parent_commit_id,
        "pullid": commit.pullid,
        "branch": commit.branch,
        "timestamp": commit.timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    assert serializer.data == expected_data


def test_invalid_update_data(transactional_db, mocker):
    commit = CommitFactory.create()
    new_data = {"pullid": "1"}
    serializer = CommitSerializer(commit, new_data)
    assert not serializer.is_valid()
    assert serializer.errors == {
        "commitid": [ErrorDetail(string="This field is required.", code="required")]
    }


def test_valid_update_data(transactional_db, mocker):
    commit = CommitFactory.create(pullid=1)
    new_data = {"pullid": "20", "commitid": "abc"}
    serializer = CommitSerializer(commit)
    res = serializer.update(commit, new_data)
    assert commit.pullid == "20"
    assert commit.commitid == "abc"
    assert commit == res


def test_commit_report_serializer(transactional_db, mocker):
    report = CommitReportFactory.create()
    serializer = CommitReportSerializer(report)
    expected_data = {
        "commit_sha": report.commit.commitid,
        "external_id": str(report.external_id),
        "created_at": report.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "code": report.code,
    }
    assert serializer.data == expected_data


def test_report_results_serializer(transactional_db, mocker):
    report_result = ReportResultsFactory.create()
    serializer = ReportResultsSerializer(report_result)
    expected_data = {
        "external_id": str(report_result.external_id),
        "report": {
            "external_id": str(report_result.report.external_id),
            "created_at": report_result.report.created_at.strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ"
            ),
            "commit_sha": report_result.report.commit.commitid,
            "code": report_result.report.code,
        },
        "state": report_result.state,
        "result": report_result.result,
        "completed_at": report_result.completed_at,
    }
    assert serializer.data == expected_data
