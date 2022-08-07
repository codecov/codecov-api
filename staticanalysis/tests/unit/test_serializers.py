import re
from uuid import UUID, uuid4

import pytest
from rest_framework.exceptions import NotFound, ValidationError

from core.tests.factories import CommitFactory, RepositoryFactory
from services.archive import ArchiveService
from staticanalysis.models import (
    StaticAnalysisSingleFileSnapshotState,
    StaticAnalysisSuite,
    StaticAnalysisSuiteFilepath,
)
from staticanalysis.serializers import (
    CommitFromShaSerializerField,
    StaticAnalysisSuiteFilepathField,
    StaticAnalysisSuiteSerializer,
)
from staticanalysis.tests.factories import (
    StaticAnalysisSingleFileSnapshotFactory,
    StaticAnalysisSuiteFilepathFactory,
)

expected_location_regex = re.compile(
    "v4/repos/[A-F0-9]{32}/static_analysis/files/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}.json"
)


def test_commit_from_sha_serializer_field_to_internal_value(mocker, db):
    commit = CommitFactory.create()
    # notice this second commit has a different repo by default
    second_commit = CommitFactory.create()
    commit.save()
    second_commit.save()
    fake_request = mocker.MagicMock(
        auth=mocker.MagicMock(
            get_repositories=mocker.MagicMock(return_value=[commit.repository])
        )
    )
    # silly workaround to not have to manually bind serializers
    mocker.patch.object(
        CommitFromShaSerializerField, "context", {"request": fake_request}
    )
    serializer_field = CommitFromShaSerializerField()
    with pytest.raises(NotFound):
        assert serializer_field.to_internal_value("abcde" * 8)
    with pytest.raises(NotFound):
        assert serializer_field.to_internal_value(second_commit.commitid)
    assert serializer_field.to_internal_value(commit.commitid) == commit


def test_filepath_field(db, mocker):
    sasfs = StaticAnalysisSingleFileSnapshotFactory.create(
        state_id=StaticAnalysisSingleFileSnapshotState.valid.value
    )
    sasfs.save()
    fp = StaticAnalysisSuiteFilepathFactory.create(
        filepath="ohoooo", file_snapshot=sasfs
    )
    fp.analysis_suite.save()
    fp.save()
    fake_archive_service = mocker.MagicMock(
        create_presigned_put=mocker.MagicMock(return_value="some_url_stuff")
    )
    serializer_field = StaticAnalysisSuiteFilepathField(
        context={"archive_service": fake_archive_service}
    )
    assert dict(serializer_field.to_representation(fp)) == {
        "file_hash": sasfs.file_hash,
        "filepath": "ohoooo",
        "raw_upload_location": "some_url_stuff",
        "state": "valid",
    }


class TestStaticAnalysisSuiteSerializer(object):
    def test_to_internal_value_missing_filepaths(self, mocker, db):
        commit = CommitFactory.create()
        commit.save()
        input_data = {"commit": commit.commitid}
        fake_request = mocker.MagicMock(
            auth=mocker.MagicMock(
                get_repositories=mocker.MagicMock(return_value=[commit.repository])
            )
        )
        serializer = StaticAnalysisSuiteSerializer(context={"request": fake_request})
        with pytest.raises(ValidationError) as exc:
            serializer.to_internal_value(input_data)
        assert exc.value.detail == {"filepaths": ["This field is required."]}

    def test_to_internal_value_complete(self, mocker, db):
        commit = CommitFactory.create()
        commit.save()
        input_data = {
            "commit": commit.commitid,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": "c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2",
                },
                {
                    "filepath": "anothersomething",
                    "file_hash": "3998813e-60db-4686-be84-1a0efa7d9b9f",
                },
            ],
        }
        fake_request = mocker.MagicMock(
            auth=mocker.MagicMock(
                get_repositories=mocker.MagicMock(return_value=[commit.repository])
            )
        )
        serializer = StaticAnalysisSuiteSerializer(context={"request": fake_request})
        res = serializer.to_internal_value(input_data)
        assert res == {
            "commit": commit,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": UUID("c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"),
                },
                {
                    "filepath": "anothersomething",
                    "file_hash": UUID("3998813e-60db-4686-be84-1a0efa7d9b9f"),
                },
            ],
        }

    def test_create_no_data_previously_exists(self, mocker, db):
        first_repository = RepositoryFactory.create()
        commit = CommitFactory.create(repository=first_repository)
        commit.save()
        validated_data = {
            "commit": commit,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": UUID("c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"),
                },
                {
                    "filepath": "anothersomething",
                    "file_hash": UUID("3998813e-60db-4686-be84-1a0efa7d9b9f"),
                },
            ],
        }
        fake_request = mocker.MagicMock(
            auth=mocker.MagicMock(
                get_repositories=mocker.MagicMock(return_value=[commit.repository])
            )
        )
        serializer = StaticAnalysisSuiteSerializer(context={"request": fake_request})
        res = serializer.create(validated_data)
        assert isinstance(res, StaticAnalysisSuite)
        assert res.commit == commit
        assert res.filepaths.count() == 2
        first_filepath, second_filepath = sorted(
            res.filepaths.all(), key=lambda x: x.filepath
        )
        assert isinstance(first_filepath, StaticAnalysisSuiteFilepath)
        assert first_filepath.filepath == "anothersomething"
        assert first_filepath.file_snapshot is not None
        archive_hash = ArchiveService.get_archive_hash(commit.repository)
        assert first_filepath.file_snapshot.repository == commit.repository
        assert first_filepath.file_snapshot.file_hash == UUID(
            "3998813e-60db-4686-be84-1a0efa7d9b9f"
        )
        assert archive_hash in first_filepath.file_snapshot.content_location
        assert (
            expected_location_regex.match(first_filepath.file_snapshot.content_location)
            is not None
        )
        assert (
            first_filepath.file_snapshot.state_id
            == StaticAnalysisSingleFileSnapshotState.created.value
        )

    def test_create_some_data_previously_exists(self, mocker, db):
        first_repository = RepositoryFactory.create()
        second_repository = RepositoryFactory.create()
        commit = CommitFactory.create(repository=first_repository)
        first_repo_first_snapshot = StaticAnalysisSingleFileSnapshotFactory.create(
            file_hash=UUID("c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"),
            repository=first_repository,
            state_id=StaticAnalysisSingleFileSnapshotState.valid.value,
            content_location="first_repo_first_snapshot",
        )
        second_repo_first_snapshot = StaticAnalysisSingleFileSnapshotFactory.create(
            file_hash=UUID("c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"),
            repository=second_repository,
            state_id=StaticAnalysisSingleFileSnapshotState.valid.value,
            content_location="second_repo_first_snapshot",
        )
        second_repo_second_snapshot = StaticAnalysisSingleFileSnapshotFactory.create(
            file_hash=UUID("3998813e-60db-4686-be84-1a0efa7d9b9f"),
            repository=second_repository,
            state_id=StaticAnalysisSingleFileSnapshotState.valid.value,
            content_location="second_repo_second_snapshot",
        )
        first_repo_separate_snapshot = StaticAnalysisSingleFileSnapshotFactory.create(
            file_hash=uuid4(),
            repository=first_repository,
            state_id=StaticAnalysisSingleFileSnapshotState.valid.value,
            content_location="first_repo_separate_snapshot",
        )
        second_repo_separate_snapshot = StaticAnalysisSingleFileSnapshotFactory.create(
            file_hash=uuid4(),
            repository=second_repository,
            state_id=StaticAnalysisSingleFileSnapshotState.valid.value,
            content_location="second_repo_separate_snapshot",
        )
        first_repo_exists_but_not_valid_yet = (
            StaticAnalysisSingleFileSnapshotFactory.create(
                file_hash=UUID("31803149-8bd7-4c2b-9a80-71f259360c72"),
                repository=first_repository,
                state_id=StaticAnalysisSingleFileSnapshotState.created.value,
                content_location="first_repo_exists_but_not_valid_yet",
            )
        )
        first_repo_first_snapshot.save()
        second_repo_first_snapshot.save()
        second_repo_second_snapshot.save()
        first_repo_separate_snapshot.save()
        second_repo_separate_snapshot.save()
        first_repo_exists_but_not_valid_yet.save()

        validated_data = {
            "commit": commit,
            "filepaths": [
                {
                    "filepath": "path/to/a.py",
                    "file_hash": UUID("c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"),
                },
                {
                    "filepath": "anothersomething",
                    "file_hash": UUID("3998813e-60db-4686-be84-1a0efa7d9b9f"),
                },
                {
                    "filepath": "oooaaa.rb",
                    "file_hash": UUID("60228df6-4d11-44d4-a048-ec2fa1ea2c32"),
                },
                {
                    "filepath": "awert.qt",
                    "file_hash": UUID("31803149-8bd7-4c2b-9a80-71f259360c72"),
                },
            ],
        }
        fake_request = mocker.MagicMock(
            auth=mocker.MagicMock(
                get_repositories=mocker.MagicMock(return_value=[commit.repository])
            )
        )
        serializer = StaticAnalysisSuiteSerializer(context={"request": fake_request})
        res = serializer.create(validated_data)
        assert isinstance(res, StaticAnalysisSuite)
        assert res.commit == commit
        assert res.filepaths.count() == 4
        first_filepath, second_filepath, third_filepath, fourth_filepath = sorted(
            res.filepaths.all(), key=lambda x: x.filepath
        )
        archive_hash = ArchiveService.get_archive_hash(first_repository)
        # first one
        assert isinstance(first_filepath, StaticAnalysisSuiteFilepath)
        assert first_filepath.filepath == "anothersomething"
        assert first_filepath.file_snapshot is not None
        assert first_filepath.file_snapshot.repository == first_repository
        assert first_filepath.file_snapshot.file_hash == UUID(
            "3998813e-60db-4686-be84-1a0efa7d9b9f"
        )
        assert archive_hash in first_filepath.file_snapshot.content_location
        assert (
            expected_location_regex.match(first_filepath.file_snapshot.content_location)
            is not None
        )
        assert (
            first_filepath.file_snapshot.state_id
            == StaticAnalysisSingleFileSnapshotState.created.value
        )
        # second one
        assert isinstance(second_filepath, StaticAnalysisSuiteFilepath)
        assert second_filepath.filepath == "awert.qt"
        assert second_filepath.file_snapshot == first_repo_exists_but_not_valid_yet
        assert second_filepath.file_snapshot.repository == first_repository
        assert second_filepath.file_snapshot.file_hash == UUID(
            "31803149-8bd7-4c2b-9a80-71f259360c72"
        )
        # content location was already there, so nothing is created
        # asserting the old value is still there
        assert (
            second_filepath.file_snapshot.content_location
            == "first_repo_exists_but_not_valid_yet"
        )
        assert (
            second_filepath.file_snapshot.state_id
            == StaticAnalysisSingleFileSnapshotState.created.value
        )
        # third one
        assert isinstance(third_filepath, StaticAnalysisSuiteFilepath)
        assert third_filepath.filepath == "oooaaa.rb"
        assert third_filepath.file_snapshot is not None
        assert third_filepath.file_snapshot.repository == first_repository
        assert third_filepath.file_snapshot.file_hash == UUID(
            "60228df6-4d11-44d4-a048-ec2fa1ea2c32"
        )
        assert archive_hash in third_filepath.file_snapshot.content_location
        assert (
            expected_location_regex.match(third_filepath.file_snapshot.content_location)
            is not None
        )
        assert (
            third_filepath.file_snapshot.state_id
            == StaticAnalysisSingleFileSnapshotState.created.value
        )
        # fourth one
        assert isinstance(fourth_filepath, StaticAnalysisSuiteFilepath)
        assert fourth_filepath.filepath == "path/to/a.py"
        assert fourth_filepath.file_snapshot == first_repo_first_snapshot
        assert fourth_filepath.file_snapshot.repository == first_repository
        assert fourth_filepath.file_snapshot.file_hash == UUID(
            "c8c23bea-c383-4abf-8a7e-6b9cadbeb5b2"
        )
        # content location was already there, so nothing is created
        # asserting the old value is still there
        assert (
            fourth_filepath.file_snapshot.content_location
            == "first_repo_first_snapshot"
        )
        assert (
            fourth_filepath.file_snapshot.state_id
            == StaticAnalysisSingleFileSnapshotState.valid.value
        )
