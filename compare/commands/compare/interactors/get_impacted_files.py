import json
import logging
from dataclasses import dataclass
from typing import List
from xmlrpc.client import Boolean

from asgiref.sync import sync_to_async
from shared.reports.types import ReportTotals

from codecov.commands.base import BaseInteractor
from compare.models import CommitComparison
from services.archive import ArchiveService

log = logging.getLogger(__name__)

# Idk if this is the place for this, but it types the response :) thoughts?
@dataclass
class ImpactedFileFromArchive:
    base_name: str
    head_name: str
    base_coverage: ReportTotals
    head_coverage: ReportTotals
    patch_coverage: ReportTotals


def check_path_in_list(report_file, path: str) -> Boolean:
    return (
        True
        if report_file["head_name"] == path or report_file["base_name"] == path
        else False
    )


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
        patch_coverage = {"hits": 0, "misses": 0, "partials": 0}
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

    def deserialize_comparison(
        self, report_data, path: str
    ) -> List[ImpactedFileFromArchive]:
        flat_impacted_files = report_data.get("files", [])
        if path:
            flat_impacted_files = list(
                filter(
                    lambda report_file: check_path_in_list(report_file, path),
                    flat_impacted_files,
                )
            )
        deserialized_impacted_files = []
        for file in flat_impacted_files:
            file["patch_coverage"] = self.compute_patch_per_file(file)
            self.deserialize_totals(file, "base_coverage")
            self.deserialize_totals(file, "head_coverage")
            self.deserialize_totals(file, "patch_coverage")
            deserialized_impacted_files.append(
                ImpactedFileFromArchive(
                    head_name=file["head_name"],
                    base_name=file["base_name"],
                    head_coverage=file["head_coverage"],
                    base_coverage=file["base_coverage"],
                    patch_coverage=file["patch_coverage"],
                )
            )
        return deserialized_impacted_files

    async def execute(
        self, comparison: CommitComparison, path: str = None
    ) -> List[ImpactedFileFromArchive]:
        if not comparison.report_storage_path:
            return []
        report_data = await self.get_comparison_data_from_archive(comparison)
        return self.deserialize_comparison(report_data, path)
