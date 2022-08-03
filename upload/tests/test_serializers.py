from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from upload.serializers import CommitSerializer


def test_contains_expected_fields(transactional_db, mocker):
    commit = CommitFactory.create()
    serializer = CommitSerializer(commit)
    print(serializer.data)
    expected_data = set(
        [
            "message",
            "timestamp",
            "ci_passed",
            "state",
            "timestamp",
            "repository",
            "author",
            "commitid",
            "parent_commit_id",
            "pullid",
            "branch",
        ]
    )
    assert set(serializer.data.keys()) == expected_data


def test_invalid_update_data(transactional_db, mocker):
    commit = CommitFactory.create()
    new_data = {"pullid": "1"}
    serializer = CommitSerializer(commit, new_data)
    assert not serializer.is_valid()
    assert serializer.errors["commitid"][0] == "This field is required."


def test_valid_update_data(transactional_db, mocker):
    commit = CommitFactory.create(pullid=1)
    new_data = {"pullid": "20", "commitid": "abc"}
    serializer = CommitSerializer(commit)
    res = serializer.update(commit, new_data)
    assert commit.pullid == "20"
    assert commit.commitid == "abc"
    assert commit == res
