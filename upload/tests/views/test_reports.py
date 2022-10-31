from django.urls import reverse


def test_reports_get_not_allowed(client):
    url = reverse("new_upload.reports", args=["the-repo", "commit-sha"])
    assert url == "/upload/the-repo/commits/commit-sha/reports"
    res = client.get(url)
    assert res.status_code == 405


def test_reports_post_empty(client):
    url = reverse("new_upload.reports", args=["the-repo", "commit-sha"])
    assert url == "/upload/the-repo/commits/commit-sha/reports"
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 404


def test_reports_results_post_empty(client):
    url = reverse(
        "new_upload.reports_results",
        args=["service", "the-repo", "commit-sha", "report_code"],
    )
    assert (
        url == "/upload/service/the-repo/commits/commit-sha/reports/report_code/results"
    )
    res = client.post(url, content_type="application/json", data={})
    assert res.status_code == 200
