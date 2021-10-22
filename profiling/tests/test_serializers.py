from core.tests.factories import RepositoryFactory
from profiling.models import ProfilingCommit
from profiling.serializers import ProfilingCommitSerializer


def test_update_profiling_commit_serializer_mocked_instance(mocker):
    serializer = ProfilingCommitSerializer()
    validated_data = {
        "code": "test_update_profiling_commit_serializer",
        "version_identifier": "tversionqwerty",
    }
    instance = mocker.MagicMock()
    res = serializer.update(instance, validated_data)
    instance.save.assert_called_with(update_fields=["version_identifier"])
    assert res == instance
    assert instance.version_identifier == "tversionqwerty"


def test_update_profiling_commit_serializer_real_instance(db, mocker):
    serializer = ProfilingCommitSerializer()
    repo = RepositoryFactory.create(active=True)
    instance = ProfilingCommit.objects.create(
        code="test_update_profiling_commit_serializer",
        repository=repo,
        version_identifier="newidea",
    )
    # putting some bad data post creation to ensure it won't get saved
    instance.code = "somefakecode"
    instance.commit_sha = "commit_sha"
    validated_data = {
        "code": "test_update_profiling_commit_serializer",
        "version_identifier": "tversionqwerty",
    }
    res = serializer.update(instance, validated_data)
    assert res == instance
    instance.refresh_from_db()
    assert instance.code == "test_update_profiling_commit_serializer"
    assert instance.version_identifier == "tversionqwerty"
    assert instance.commit_sha is None
