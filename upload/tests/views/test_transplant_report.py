from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import RepositoryFactory

from upload.views.uploads import CanDoCoverageUploadsPermission


def test_uploads_get_not_allowed(db, mocker):
    mocker.patch.object(
        CanDoCoverageUploadsPermission, "has_permission", return_value=True
    )
    task_mock = mocker.patch("services.task.TaskService.transplant_report")

    repository = RepositoryFactory(
        name="the-repo", author__username="codecov", author__service="github"
    )
    owner = repository.author
    client = APIClient()
    client.force_authenticate(user=owner)

    url = reverse(
        "new_upload.transplant_report",
        args=["github", "codecov::::the-repo"],
    )
    assert url == "/upload/github/codecov::::the-repo/commits/transplant"

    res = client.post(
        url, data={"from_sha": "sha to copy from", "to_sha": "sha to copy to"}
    )
    assert res.status_code == 200

    task_mock.assert_called_once_with(
        repo_id=repository.repoid, from_sha="sha to copy from", to_sha="sha to copy to"
    )
