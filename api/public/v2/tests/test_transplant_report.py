from django.urls import reverse
from utils.test_utils import APIClient
from shared.django_apps.core.tests.factories import RepositoryFactory, OwnerFactory


def test_transplant_report(db, mocker):
    mocker.patch(
        "api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions", return_value=(True,True)
    )
    task_mock = mocker.patch("services.task.TaskService.transplant_report")


    org = OwnerFactory(username="codecov", service="github")
    repo = RepositoryFactory(author=org, name="test-repo", active=True)
    current_owner = OwnerFactory(
        username="codecov-user",
        service="github",
        organizations=[org.ownerid],
        permission=[repo.repoid],
    )

    url = reverse(
        "api-v2-transplant",
        kwargs={
            "service": "github",
            "owner_username": org.username,
            "repo_name": repo.name,
        }
    )
    assert url == "/api/v2/github/codecov/repos/test-repo/commits/transplant"

    client = APIClient()
    client.force_login_owner(current_owner)
    res = client.post(
        url, data={"from_sha": "sha to copy from", "to_sha": "sha to copy to"}
    )
    assert res.status_code == 200

    task_mock.assert_called_once_with(
        repo_id=repo.repoid, from_sha="sha to copy from", to_sha="sha to copy to"
    )
