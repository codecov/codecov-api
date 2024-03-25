from django.urls import reverse
from shared.django_apps.reports.models import *


class ProxyReportSession(ReportSession):
    class Meta:
        proxy = True

    @property
    def download_url(self):
        repository = self.report.commit.repository
        return (
            reverse(
                "upload-download",
                kwargs={
                    "service": get_short_service_name(repository.author.service),
                    "owner_username": repository.author.username,
                    "repo_name": repository.name,
                },
            )
            + f"?path={self.storage_path}"
        )
