import json
import logging

from asgiref.sync import sync_to_async
from shared.reports.types import ReportTotals

from codecov.commands.base import BaseInteractor
from services.archive import ArchiveService

log = logging.getLogger(__name__)


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

    def compute_patch_per_file(self, file):
        added_diff_coverage = file.get("added_diff_coverage", [])
        if not added_diff_coverage:
            return None
        patch_coverage = {
            "hits": 0,
            "misses": 0,
            "partials": 0,
        }
        for added_coverage in added_diff_coverage:
            [_, type_coverage] = added_coverage
            if type_coverage == "h":
                patch_coverage["hits"] += 1
            if type_coverage == "m":
                patch_coverage["misses"] += 1
            if type_coverage == "p":
                patch_coverage["partials"] += 1
        return patch_coverage

    def deserialize_totals(self, file, key):
        if not file.get(key):
            return
        # convert dict to ReportTotals and compute the coverage
        totals = ReportTotals(**file[key])
        nb_branches = totals.hits + totals.misses + totals.partials
        totals.coverage = (100 * totals.hits / nb_branches) if nb_branches > 0 else None
        file[key] = totals

    def deserialize_comparison(self, impacted_files):
        flat_impacted_files = impacted_files.get("files", [])
        for file in flat_impacted_files:
            file["patch_coverage"] = self.compute_patch_per_file(file)
            self.deserialize_totals(file, "base_coverage")
            self.deserialize_totals(file, "head_coverage")
            self.deserialize_totals(file, "patch_coverage")
        return flat_impacted_files

    async def execute(self, comparison):
        if not comparison.report_storage_path:
            return []
        data = await self.get_comparison_data_from_archive(comparison)
        return self.deserialize_comparison(data)
