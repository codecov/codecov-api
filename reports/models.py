from django.urls import reverse
from shared.django_apps.reports.models import *
from shared.django_apps.reports.models import REPORTS_APP_LABEL


class ProxyReportSession(ReportSession):
    class Meta:
        proxy = True
        app_label = REPORTS_APP_LABEL

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
