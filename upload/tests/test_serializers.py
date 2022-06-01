from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory
from upload.serializers import UploadSerializer


def get_fake_upload():
    user_with_no_uplaods = OwnerFactory()
    user_with_uplaods = OwnerFactory()
    repo = RepositoryFactory.create(author=user_with_uplaods, private=True)
    public_repo = RepositoryFactory.create(author=user_with_uplaods, private=False)
    commit = CommitFactory.create(repository=repo)
    report = CommitReportFactory.create(commit=commit)

    return UploadFactory.create(report=report)


def test_serialize_upload(transactional_db):
    fake_upload = get_fake_upload()
    serializer = UploadSerializer(instance=fake_upload)
    assert (
        "upload_type" in serializer.data
        and serializer.data["upload_type"] == "uploaded"
    )
    assert "download_url" in serializer.data
    new_data = {"env": {"some_var": "some_value"}, "name": "upload name...?"}
    res = serializer.update(fake_upload, new_data)
    assert res == fake_upload
    assert fake_upload.name == "upload name...?"
