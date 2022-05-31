import pytest
from django.urls import reverse


def test_commit_view(client):
    with pytest.raises(NotImplementedError) as err:
        url = reverse("public_api.commits", args=["the-repo"])
        client.get(url)
    assert str(err.value) == str(["the-repo"])


def test_reports_view(client):
    with pytest.raises(NotImplementedError) as err:
        url = reverse(
            "public_api.reports", kwargs=dict(repo="the-repo", commit_id="commit-sha")
        )
        client.get(url)
    assert str(err.value) == str(["the-repo", "commit-sha"])


def test_uploads_view(client):
    with pytest.raises(NotImplementedError) as err:
        url = reverse(
            "public_api.uploads",
            kwargs=dict(repo="the-repo", commit_id="commit-sha", report_id="repo-id"),
        )
        client.get(url)
    assert str(err.value) == str(["the-repo", "commit-sha", "repo-id"])
