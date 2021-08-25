import logging
import json
from asgiref.sync import sync_to_async

from shared.reports.types import ReportTotals

from codecov.commands.base import BaseInteractor
from services.archive import ArchiveService


log = logging.getLogger(__name__)


def deserialize_totals(file, key):
    if file[key]:
        file[key] = ReportTotals(*file[key])


class GetImpactedFilesInteractor(BaseInteractor):
    @sync_to_async
    def get_comparison_data_from_archive(self, comparison):
        repository = comparison.compare_commit.repository
        archive_service = ArchiveService(repository)
        try:
            data = archive_service.read_file(comparison.report_storage_path)
            return json.loads(data)
        # pylint: disable=W0702
        except:
            log.error(
                "GetImpactedFiles - couldnt fetch data from storage", exc_info=True
            )
            return {}

    def deserialize_comparison(self, impacted_files):
        flat_impacted_files = impacted_files.get("changes", []) + impacted_files.get(
            "diff", []
        )
        for file in flat_impacted_files:
            deserialize_totals(file, "base_totals")
            deserialize_totals(file, "compare_totals")
            deserialize_totals(file, "patch")
        return flat_impacted_files

    async def execute(self, comparison):
        if not comparison.report_storage_path:
            return []
        data = await self.get_comparison_data_from_archive(comparison)
        return self.deserialize_comparison(data)
