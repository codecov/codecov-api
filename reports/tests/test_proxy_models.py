from django.test import TestCase

from reports.models import ProxyReportSession
from reports.tests.factories import UploadFactory


class ProxyUploadTest(TestCase):
    def test_get_download_url(self):
        storage_path = "v4/123/123.txt"
        session = UploadFactory(storage_path=storage_path)
        proxy_report_session = ProxyReportSession.objects.filter(
            report_id=session.report_id
        ).first()
        repository = proxy_report_session.report.commit.repository
        assert (
            proxy_report_session.download_url
            == f"/upload/gh/{repository.author.username}/{repository.name}/download?path={storage_path}"
        )
