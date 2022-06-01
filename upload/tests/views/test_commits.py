from wsgiref import headers

from django.urls import reverse


def test_commits_get_not_allowed(client):
    url = reverse("new_upload.commits", args=["the-repo"])
    assert url == "/upload/the-repo/commits"
    res = client.get(url)
    assert res.status_code == 405


def test_commit_post_empty(client):
    url = reverse("new_upload.commits", args=["the-repo"])
    assert url == "/upload/the-repo/commits"
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404
