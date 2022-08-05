from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from upload.serializers import CommitSerializer


def test_contains_expected_fields(transactional_db, mocker):
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
    assert serializer.errors["commitid"][0] == "This field is required."


def test_valid_update_data(transactional_db, mocker):
    commit = CommitFactory.create(pullid=1)
    new_data = {"pullid": "20", "commitid": "abc"}
    serializer = CommitSerializer(commit)
    res = serializer.update(commit, new_data)
    assert commit.pullid == "20"
    assert commit.commitid == "abc"
    assert commit == res
