from django.urls import reverse


def test_reports_get_not_allowed(client):
    url = reverse("new_upload.reports", args=["service", "the-repo", "commit-sha"])
    assert url == "/upload/service/the-repo/commits/commit-sha/reports"
    res = client.get(url)
    assert res.status_code == 405


def test_reports_post_empty(client):
    url = reverse("new_upload.reports", args=["service", "the-repo", "commit-sha"])
    assert url == "/upload/service/the-repo/commits/commit-sha/reports"
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404
