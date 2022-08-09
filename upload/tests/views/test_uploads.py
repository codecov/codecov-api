from django.urls import reverse


def test_upload_get_not_allowed(client):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "reportid"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/reportid/uploads"
    res = client.get(url)
    assert res.status_code == 405


def test_upload_post_empty(client):
    url = reverse("new_upload.uploads", args=["the-repo", "commit-sha", "reportid"])
    assert url == "/upload/the-repo/commits/commit-sha/reports/reportid/uploads"
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404
